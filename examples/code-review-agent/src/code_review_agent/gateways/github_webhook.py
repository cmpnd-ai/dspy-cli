"""GitHub Webhook Gateway for automated PR reviews."""

import hashlib
import hmac
import json
import logging
import os
from typing import Any, Callable, Dict, Optional, Type

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from dspy_cli.gateway import APIGateway

logger = logging.getLogger(__name__)


class GitHubWebhookGateway(APIGateway):
    """Gateway for GitHub webhook-triggered PR reviews.

    Handles:
    - Webhook signature verification (X-Hub-Signature-256)
    - Event filtering (PR opened / reviewer requested)
    - Background processing with 202 response
    - Deduplication via Redis
    - GitHub App authentication for posting reviews
    """

    path = "/webhooks/github"
    method = "POST"
    requires_auth = False  # Webhook uses signature verification instead

    def __init__(self):
        self._webhook_secret: Optional[str] = None
        self._bot_username: Optional[str] = None
        self._github_auth = None
        self._redis = None
        self._original_endpoint: Optional[Callable] = None

    def setup(self) -> None:
        """Initialize GitHub App auth and Redis connection."""
        # Webhook signature verification (optional for local dev)
        self._webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        if not self._webhook_secret:
            logger.warning("GITHUB_WEBHOOK_SECRET not set - signature verification disabled (OK for local dev)")

        # Bot username for reviewer request filtering
        self._bot_username = os.environ.get("GITHUB_BOT_USERNAME")
        if not self._bot_username:
            raise ValueError("GITHUB_BOT_USERNAME environment variable required")

        # GitHub App authentication
        app_id = os.environ.get("GITHUB_APP_ID")
        private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
        if not app_id or not private_key:
            raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY required")

        from code_review_agent.utils.github_app_auth import GitHubAppAuth

        self._github_auth = GitHubAppAuth(app_id=app_id, private_key=private_key)

        # Redis for deduplication (optional)
        # Upstash uses UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN
        redis_url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("UPSTASH_REDIS_URL")
        redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("UPSTASH_REDIS_TOKEN")
        if redis_url and redis_token:
            from code_review_agent.utils.redis_dedup import RedisDedup

            self._redis = RedisDedup(url=redis_url, token=redis_token)
            logger.info("Redis deduplication enabled")
        else:
            logger.warning("Redis not configured - deduplication disabled")

    def shutdown(self) -> None:
        """Close Redis connection."""
        if self._redis:
            self._redis.close()

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature using HMAC-SHA256."""
        # Skip verification if no secret configured (local dev mode)
        if not self._webhook_secret:
            return True

        if not signature or not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)

    def should_process_event(self, event_type: str, payload: Dict) -> tuple[bool, str]:
        """Check if this webhook event should trigger a review.

        Returns:
            Tuple of (should_process, reason)
        """
        if event_type != "pull_request":
            return False, f"Ignoring event type: {event_type}"

        action = payload.get("action", "")

        # Trigger on PR opened
        if action == "opened":
            return True, "PR opened"

        # Trigger on reviewer requested (if it's our bot)
        if action == "review_requested":
            requested_reviewer = payload.get("requested_reviewer", {})
            if requested_reviewer.get("login") == self._bot_username:
                return True, f"Bot {self._bot_username} requested as reviewer"
            return False, f"Reviewer requested but not our bot: {requested_reviewer.get('login')}"

        return False, f"Ignoring action: {action}"

    def to_pipeline_inputs(self, request: Any) -> Dict[str, Any]:
        """Transform webhook payload to PRReviewer inputs."""
        # Handle both webhook payload (dict) and Pydantic model
        if hasattr(request, "model_dump"):
            return request.model_dump()

        pr = request.get("pull_request", {})
        repo = request.get("repository", {})

        return {
            "repo": repo.get("full_name"),
            "pr_number": pr.get("number"),
        }

    def configure_route(
        self,
        app: FastAPI,
        route_path: str,
        endpoint: Callable[..., Any],
        response_model: Optional[Type[Any]] = None,
    ) -> None:
        """Configure custom webhook endpoint with background processing."""
        # Store original endpoint for background task
        self._original_endpoint = endpoint

        gateway = self  # Capture for closure

        async def webhook_handler(
            request: Request,
            background_tasks: BackgroundTasks,
        ) -> Response:
            """Handle GitHub webhook with signature verification and background processing."""
            # Read raw body for signature verification
            body = await request.body()
            signature = request.headers.get("X-Hub-Signature-256", "")

            # Verify signature
            if not gateway.verify_signature(body, signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

            # Parse payload
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON")

            # Check event type
            event_type = request.headers.get("X-GitHub-Event", "")
            should_process, reason = gateway.should_process_event(event_type, payload)

            if not should_process:
                logger.info(f"Skipping webhook: {reason}")
                return Response(
                    content=json.dumps({"status": "skipped", "message": reason}),
                    status_code=200,
                    media_type="application/json",
                )

            # Extract PR info for deduplication
            pr = payload.get("pull_request", {})
            repo = payload.get("repository", {})
            pr_key = f"{repo.get('full_name')}:{pr.get('number')}"

            # Check deduplication
            if gateway._redis and not gateway._redis.try_acquire(pr_key, ttl_seconds=600):
                logger.info(f"Review already in progress for {pr_key}")
                return Response(
                    content=json.dumps(
                        {"status": "skipped", "message": "Review already in progress"}
                    ),
                    status_code=200,
                    media_type="application/json",
                )

            # Get installation ID for GitHub App auth
            installation_id = payload.get("installation", {}).get("id")
            if not installation_id:
                logger.error("No installation ID in webhook payload")
                if gateway._redis:
                    gateway._redis.release(pr_key)
                raise HTTPException(status_code=400, detail="Missing installation ID")

            logger.info(f"Scheduling review for {pr_key}: {reason}")

            # Schedule background processing
            background_tasks.add_task(
                gateway._process_review,
                payload=payload,
                installation_id=installation_id,
                pr_key=pr_key,
            )

            # Return 202 Accepted immediately
            return Response(
                content=json.dumps({"status": "accepted", "message": "Review scheduled"}),
                status_code=202,
                media_type="application/json",
            )

        # Register the custom route
        app.add_api_route(
            route_path,
            webhook_handler,
            methods=[self.method],
            response_model=None,  # We handle response manually
        )

    async def _process_review(
        self,
        payload: Dict,
        installation_id: int,
        pr_key: str,
    ) -> None:
        """Background task to run review and post results to GitHub."""
        try:
            # Get installation token
            token = self._github_auth.get_installation_token(installation_id)

            # Prepare pipeline inputs
            pipeline_inputs = self.to_pipeline_inputs(payload)

            logger.info(f"Running review for {pr_key}: {pipeline_inputs}")

            # Call the original endpoint (bypasses FastAPI validation since we call directly)
            # The endpoint's to_pipeline_inputs will handle our dict
            output = await self._original_endpoint(pipeline_inputs)

            logger.info(f"Review completed for {pr_key}, posting to GitHub")

            # Post the review to GitHub
            from code_review_agent.utils.github_review_poster import post_github_review

            await post_github_review(
                token=token,
                repo=payload.get("repository", {}).get("full_name"),
                pr_number=payload.get("pull_request", {}).get("number"),
                head_sha=payload.get("pull_request", {}).get("head", {}).get("sha"),
                review=output,
            )

            logger.info(f"Successfully posted review for {pr_key}")

        except Exception as e:
            # Silent failure - log but don't post error to GitHub
            logger.error(f"Error processing review for {pr_key}: {e}", exc_info=True)

        finally:
            # Release deduplication lock
            if self._redis:
                self._redis.release(pr_key)
