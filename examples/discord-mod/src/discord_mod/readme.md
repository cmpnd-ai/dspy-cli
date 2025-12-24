## TODO

- [ ] Finish `on_complete` explanation in Gateway section (line ~154)
- [ ] Remove leftover outline bullets in Production section (lines ~161-165)
- [ ] Make sure that the thing is still running
- [ ] Paste signature and prompt examples in Appendix
- [ ] Delete notes at top once draft is final

---

# Building a Discord moderation bot with DSPy

## The Problem

I am one of the mods for the DSPy community discord. One of the most common things that happens is that people end up posting jobs in the #general channel. We want people to post jobs! But we do not want the main channel to be cluttered with intros or people advertising.

It doesn't take long to delete the message and send a dm asking them to move it, but it certainly gets annoying.

Classifying whether or not something is a job posting is pretty easy. We can expect most modern LLMs to do a good job at this.

Like a REALLY good job. So i expect any errors to come from mostly underspecification rather than from LLM errors.

For instance:
> Oh yeah I see why GEPA is cool. In my last job, I used MIPRO to improve our LLM-as-a-judge for insurance document relevance inside a chat by 20%, and my manager + our customers were very happy. Ultimately, I’m now looking for the next challenge and I’m excited about applying GEPA to whatever my next problem is (P.S. pls DM if you’d like to chat about hiring me!).

The primary of the intent of the message is to say that GEPA is cool and validate that they have done it at a company + share the project that they worked on, and secondarily is to get hired. As a team we talked about this, and its about the primary intent, rather than the presence of anything hiring related.

The other design consideration is that while it would be annoying for people to get messages false positives for a case I haven't considered, its not the end of the world. Certainly I can notice a new error case, and just adjust the bot and redeploy in a relatively timely manner. Any change does not need to be thoroughly tested, because the stakes are quite low so long as it doesn't delete the whole discord server.

## Designing the LLM pipeline

The most common case that this is trying to solve for is people posting job descriptions or looking for work posts inside of the general channel.

This isn't meant to ban users. If it happens to catch and delete a stray non-job spam message, thats upside, but really the usecase is about moving job postings into the correct channel.

So what do we want this system to do? We want it to detect the intent of a message, and suggest an action. We also want to be notified as mods if there is an action taken, so that we can be aware if things start to break.

Our pipeline starts to look something like:

`message, metadata -> (model_reasoning), intent, action, action_reason`

Let's start to put that into a DSPy signature:

```python
class JobPostingSignature(dspy.Signature):
    """Classify a Discord message and determine moderation action.
    
    A job posting or job seeking message will express the primary intent of introducing the user, their qualifications/openness to work, and their availability for hire, or availability to hire others"""

    message: str = dspy.InputField(desc="The Discord message content")
    author: str = dspy.InputField(desc="The message author's username")
    channel_name: str = dspy.InputField(desc="The channel where the message was posted")

    intent: Literal["post_job", "seek_job", "other"] = dspy.OutputField(
        desc="The user's intent: 'post_job' if offering a job, 'seek_job' if looking for work, 'other' for general discussion"
    )
    action: Literal["allow", "move", "flag", "delete"] = dspy.OutputField(
        desc="Action to take: 'allow' if appropriate for channel, 'move' if should be in jobs channel, 'flag' for manual review, 'delete' if spam/violation"
    )
    reason: str = dspy.OutputField(
        desc="Brief explanation of the classification and recommended action"
    )
```

We pass in the message, author, and the channel it was posted in. All of these could provide relevant information. If a user named `dm_me_for_free_crypto` sends a sketchy message, the LLM should take the username into account. Same with channel.

In #help-channel, if someone is struggling with a problem that requires a lot of extra help. its totally fine for them to ask for help and offer compensation. It's just the explicit usage of only posting in `#help-channel` that you're looking for an AI engineer that we want to target.

It's because of this contextual nuance that things look a little fuzzy, rather than the purer classification of `message -> job_posting: bool` pipeline.

Note that there are two reasoning fields. This is important. The first model reasoning happens when we call the signature with `dspy.ChainOfThought(JobPostingSignature)`. This is to give the model time to deliberate. We are using gpt-5 nano with no reasoning built in, so this will explicitly give the model a chance to discuss the message if there is any nuance. The second reasoning field is meant to be user/moderator facing. After the model has committed to a course of action, we want to show the user "why did you get banned" which is different reasoning than the model's debate about what the intent of the message is.

### Why use DSPy instead of just writing the prompts myself

Part of why using DSPy is just because everything is built in already. Structured outputs, retries, plumbling between different LLMs and providers if I ever want to update, are all for free.

My code can be incredibly simple.

The module which takes in the signature above looks like:

```python
class ClassifyJobPosting(dspy.Module):
    """Classify Discord messages as job postings, job-seeking, or general chat."""

    gateway = JobPostingGateway

    def __init__(self):
        super().__init__()
        self.classifier = dspy.ChainOfThought(JobPostingSignature)

    def forward(self, message: str, author: str, channel_name: str) -> dspy.Prediction:
        return self.classifier(message=message, author=author, channel_name=channel_name,)
```

Then the only thing that I need around this is the discord network code.

Its like 8 real lines of code for an LLM pipeline, plumbing included, wrapping around the structured inputs and outputs.

## Building the gateway

The LLM logic is pretty simple. The most complex part is designing the system with discord.

There are two main ways that we can build this bot:
1. Realtime streaming
2. Running on a cronjob

We opt for (2) the cron approach. Mostly because the realtime streaming requires us to maintain a websocket connection. If the dspy server was so popular that we had a large volume of messages, I might take on the higher complexity of building that. The dspy server averages less than 20 messages every 5 minutes. If we instead just build something that will check the last 20 messages every 5 minutes, its totally fine. If a job posting is live on the server for 5 minutes, noone cares. This constraint would be different for different servers, but these are the constraints of the problem we are trying to solve without overengineering.

We need to set up a discord bot token with access to read messages, send messages, and delete messages.

You can see the discord tutorial for how to do that (here)[https://discord.com/developers/docs/quick-start/getting-started].

The actual behavior of this will be as follows:
Every 5 minutes:
1. Gather the last 20 messages
2. Skip any that have already been processed
3. Classify as "move", "flag", "delete", or "allow"
4. Take the relevant action for "move", "flag", "delete", and send an audit message into the moderator only channel
- Move moves the message into the #jobs channel, "flag" adds an emoji reaction and sends an audit message for the mods to review, "delete", well, deletes, and "allow" does nothing.

The routing logic is simplified by using `dspy-cli`.

There are a few different kinds of entry points you may want for any DSPy application. The two that `dspy-cli` currently supports are **api-based** and **cron-based**.

You might just want to have your modules as named endpoints so you can send a POST request to `/{ModuleName}`. In this case, your post requests would directly have the inputs that you want for your `Module.forward` method. You might also want to have a webhook setup, where your endpoint takes in some webhook payload, say from GitHub, extracts some data from it, such as fetching the code of the PR that triggered the webhook, and then passes that code into your module. Your real code might look like: `dspy.ReAct("files: Dict[str, str] -> review", tools=[file_search, web_search, run_code, ...])` You need to get all of the files and put them into whatever format makes sense. For this, you want a layer to sit in between the api and your LLM logic. Here `APIGateway` makes sense as your middleware for your LLM logic,

For this discord case, we want to gather a bunch of inputs every so often, and run batch inference over them.

### JobPostingGateway

JobPostingGateway subclasses CronGateway. This is how you specify your specific data loading behavior. In our case, it will load the data, and take actions after.

CronGateway is an ABC with two core methods:

1. **`get_pipeline_inputs`**: Fetches your data and returns a list of input dictionaries for the pipeline to process. Each dict contains the kwargs for your module's `forward()` method. You can also include a `_meta` key for data needed in `on_complete` but not by the pipeline itself (like message IDs or channel IDs).

2. **`on_complete`**: Runs after each successful pipeline execution. This is where you take action based on the LLM's output. It receives both the original inputs (including `_meta`) and the pipeline output.

There's also an optional `on_error` method for handling failures.

Here's a simplified version of our gateway:

```python
class JobPostingGateway(CronGateway):
    schedule = "*/5 * * * *"  # Every 5 minutes

    def setup(self) -> None:
        """Validate config and create Discord client."""
        self.client = DiscordClient(token=os.environ["DISCORD_BOT_TOKEN"])
        self.channel_ids = os.environ["DISCORD_CHANNEL_IDS"].split(",")

    async def get_pipeline_inputs(self) -> list[dict]:
        """Fetch recent messages from monitored channels."""
        inputs = []
        for channel_id in self.channel_ids:
            messages = await self.client.get_recent_messages(channel_id, limit=20)
            for msg in messages:
                if msg["author"].get("bot"):
                    continue
                inputs.append({
                    "message": msg["content"],
                    "author": msg["author"]["username"],
                    "channel_name": msg.get("channel_name", "unknown"),
                    "_meta": {
                        "message_id": msg["id"],
                        "channel_id": channel_id,
                        "author_id": msg["author"]["id"],
                    },
                })
        return inputs

    async def on_complete(self, inputs: dict, output: PipelineOutput) -> None:
        """Take moderation action based on classification result."""
        meta = inputs["_meta"]
        action = output.get("action", "allow")

        if action == "allow":
            return

        if action == "move":
            # Repost in jobs channel, delete original, DM user
            await self.client.send_message(
                self.jobs_channel_id,
                f"**Moved from <#{meta['channel_id']}>**\n{inputs['message']}",
            )
            await self.client.delete_message(meta["channel_id"], meta["message_id"])
            await self.client.send_dm(
                meta["author_id"],
                "Your job posting was moved to the jobs channel.",
            )

        elif action == "flag":
            await self.client.add_reaction(meta["channel_id"], meta["message_id"], "⚠️")

        elif action == "delete":
            await self.client.delete_message(meta["channel_id"], meta["message_id"])
            await self.client.send_dm(meta["author_id"], output.get("reason", ""))
```

### Batch Processing

For higher throughput, CronGateway supports batch mode which processes all inputs in parallel using DSPy's `module.batch()`:

```python
class JobPostingGateway(CronGateway):
    schedule = "*/5 * * * *"
    use_batch = True      # Enable parallel processing
    num_threads = 4       # Number of concurrent threads (optional)
    max_errors = 10       # Stop batch if this many errors occur (optional)
```

With batch mode enabled, the scheduler will call your module's `batch()` method instead of running `forward()` sequentially. This is useful when you have many inputs and want to parallelize LLM calls. The `on_complete` callback still runs once per input after all batch results return 

## Production considerations

"production" is a loose word here because of the small scale, but this is deployed live.


5. Production Considerations (2-3 min)
     - Dry-run mode
     - Audit logging
     - DM notifications to users
     - Fly.io deployment

Because this is such a small project, there wasn't a great dev environment nor was it worth it to set up one. I sent messages into #general to test this. Before I enabled any actions that would actually remove messages, I set up a dry run mode that would analyze messages and send a dry run audit message into #moderator-only. I saw that it was correctly flagging the examples that I put in, and that was enough to turn off dry run mode.

We also want to notify users after they have a message moved. This is a simple DM, but important from a UX perspective.

### Deployment

We deploy this onto Fly.io. We want this to be a permananelty running machine that will trigger itself with the python process every 5 minutes.

# TODO: Make sure that it is still running

Fly automatically scales your workload to 2 machines, and will pause if there is not enough external traffic. For this deployment, there will definitionally be 0 traffic, so we need to get around the auto-scaling. We also don't want 2 machines. (1) I don't want to pay for that and (2) We havent built in any persistence or deduplication mechanisms. If there are two machines running, they might both pick up the same messages.

We need to set some environment variables in order to tell which channels to look at.


## Results and Lessons

After I made this bot, there were uh no job postings that it flagged because I think people are not active on discord this week. It was launched right before the holidays. I hope to see some more job postings to move in the next few weeks.

OR they got so scared by my bot that noone dared try anything.

We will see if its useful when things pick back up in the new year.

Notes:
Is this the most robust setup? Nah this is a discord bot without a ton of traffic.
Could someone prompt inject this? Like very potentially! Does it matter? No not at all. The bot has no tool access, and its not like the prompt is secret. There are no tools to access other messages, etc

## Appendix

If you are curious about how the dspy signature gets turned into a prompt, it looks like the following.

The signature is:
```python
class JobPostingSignature(dspy.Signature):
    """Classify a Discord message and determine moderation action.
    
    A job posting or job seeking message will express the primary intent of introducing the user, their qualifications/openness to work, and their availability for hire, or availability to hire others"""

    message: str = dspy.InputField(desc="The Discord message content")
    author: str = dspy.InputField(desc="The message author's username")
    channel_name: str = dspy.InputField(desc="The channel where the message was posted")

    intent: Literal["post_job", "seek_job", "other"] = dspy.OutputField(
        desc="The user's intent: 'post_job' if offering a job, 'seek_job' if looking for work, 'other' for general discussion"
    )
    action: Literal["allow", "move", "flag", "delete"] = dspy.OutputField(
        desc="Action to take: 'allow' if appropriate for channel, 'move' if should be in jobs channel, 'flag' for manual review, 'delete' if spam/violation"
    )
    reason: str = dspy.OutputField(
        desc="Brief explanation of the classification and recommended action"
    )
```

DSPy has a concept of an "adapter" which is a class that determines how a signature gets turned into a prompt, and also how the answers get extracted on the other end.

The rough outline for the adapters is:
```python
System prompt:
1. Inputs
2. Outputs
3. Task

User prompt:
Field name: value for field, value in inputs
```

The exact prompt that gets sent to the LLM is:
```
System message:

Your input fields are:
1. `message` (str): The Discord message content
2. `author` (str): The message author's username
3. `channel_name` (str): The channel where the message was posted
Your output fields are:
1. `intent` (Literal['post_job', 'seek_job', 'other']): The user's intent: 'post_job' if offering a job, 'seek_job' if looking for work, 'other' for general discussion
2. `action` (Literal['allow', 'move', 'flag', 'delete']): Action to take: 'allow' if appropriate for channel, 'move' if should be in jobs channel, 'flag' for manual review, 'delete' if spam/violation
3. `reason` (str): Brief explanation of the classification and recommended action
All interactions will be structured in the following way, with the appropriate values filled in.

[[ ## message ## ]]
{message}

[[ ## author ## ]]
{author}

[[ ## channel_name ## ]]
{channel_name}

[[ ## intent ## ]]
{intent}        # note: the value you produce must exactly match (no extra characters) one of: post_job; seek_job; other

[[ ## action ## ]]
{action}        # note: the value you produce must exactly match (no extra characters) one of: allow; move; flag; delete

[[ ## reason ## ]]
{reason}

[[ ## completed ## ]]
In adhering to this structure, your objective is:
        Classify a Discord message and determine moderation action.

        A job posting or job seeking message will express the primary intent of introducing the user, their qualifications/openness to work, and their availability for hire, or availability to hire others

User message:

[[ ## message ## ]]
Hey everyone! I'm a senior Python developer with 5 years of experience looking for new opportunities. Open to remote work!

[[ ## author ## ]]
job_seeker_123

[[ ## channel_name ## ]]
general-chat

Respond with the corresponding output fields, starting with the field `[[ ## intent ## ]]` (must be formatted as a valid Python Literal['post_job', 'seek_job', 'other']), then `[[ ## action ## ]]` (must be formatted as a valid Python Literal['allow', 'move', 'flag', 'delete']), then `[[ ## reason ## ]]`, and then ending with the marker for `[[ ## completed ## ]]`.
```

And the LM responds with:
```
[[ ## intent ## ]]
seek_job

[[ ## action ## ]]
move

[[ ## reason ## ]]
The message expresses the user's intent to seek job opportunities, which is more appropriate for a jobs channel rather than a general chat.

[[ ## completed ## ]]
```