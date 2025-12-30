# Moderating Discord with DSPy

There is a common annoyance among every Discord moderator: people posting in the wrong channels.

In the DSPy community Discord, this happens most frequently with job related postings: people looking to hire and people looking to be hired. To be clear: we like job posts! We just don't want listings and resumes cluttering the main channel.

It doesn't take long to delete the message and send a DM asking them to move it, but it certainly gets annoying.

The good news is that getting AI to detect and take the action is pretty easy. 

## Specifying our task

We expect most modern LLMs to do a good job at this. Like a REALLY good job. So I expect any errors to come from underspecification rather than LLM errors.

This bot isn't meant to ban users or be a catch-all spam detector. If it happens to catch and delete a stray non-job spam message, that's upside, but really the use case is about moving job postings into the correct channel.

### Sketching out the shape

The main goal of this system is to **detect the primary intent of a message**. The intent can be job posting, job seeking, or neither. We also want the system to suggest an action, between deleting, moving, flagging, or allowing, depending on context.

We also want to be notified as mods if there is an action taken, so that we can be aware if things start to break.

#### Where There's Nuance

Primary intent is a fuzzy line to draw. There are messages that have self-promotion in them, but the primary intent is not to promote. This line was chosen by talking to the team during the creation of this project.

For example:
> Oh yeah I see why GEPA is cool. In my last job, I used MIPRO to improve our LLM-as-a-judge for insurance document relevance inside a chat by 20%, and my manager + our customers were very happy. Ultimately, I’m now looking for the next challenge and I’m excited about applying GEPA to whatever my next problem is (P.S. pls DM if you’d like to chat about hiring me!).

In this case, The primary intent of the message is to validate that they've used GEPA at a company, and share the project they worked on. Getting hired is secondary. As a team we talked about this, and it's about the primary intent, rather than the presence of anything hiring-related.

We will want to use in the message, author, and the channel it was posted in. All of these could provide relevant information. If a user named `dm_me_for_free_crypto` sends a sketchy message, the LLM should take the username into account. Same with channel.

In `#help-channel`, if someone is struggling with a problem that requires a lot of extra help, it's totally fine for them to ask for help and offer compensation. It's only when someone posts exclusively in `#help-channel` saying they're looking for an AI engineer that we want to flag it.

It's because of this contextual nuance that things look a little fuzzy, rather than the purer of `message: str -> is_job_related: bool` pipeline.

Or the simpler pipeline: `if 'hiring' or 'job' in message: return True`

#### Defining it as a signature

Our task, inputs, and outputs for the LLM starts to look something like:

```
TASK:
Determine if a discord message is either a job posting, looking for a job, or neither.

INPUTS:
- message: str
- metadata

OUTPUTS:
- internal_model_reasoning: str
- intent: POST, SEEK or NEITHER
- action: MOVE, FLAG, DELETE, ALLOW
- action_reason: str (user facing)
```

### Convert to DSPy

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

Note that there are two reasoning fields. This is a design choice. 

The first model reasoning happens when we call the signature with `dspy.ChainOfThought(JobPostingSignature)`. This is to give the model time to deliberate. We are using `gpt-5-nano` with no reasoning built in, so this will explicitly give the model a chance to discuss the message if there is any nuance. This is similar to setting the model thinking parameter.

The second reasoning field is meant to be user/moderator facing. After the model has committed to a course of action, we want to show the user and us as the mods, "why did you get banned" which is different reasoning than the model's internal debate about what the intent of the message is.

#### Why use DSPy instead of just writing the prompts myself

Part of why I use DSPy is that everything is built in already. Structured outputs, retries, plumbing between different LLMs and providers if I ever want to update, are all for free.

My code can be incredibly simple.

The module which takes in the signature above looks like:

```python
class ClassifyJobPosting(dspy.Module):
    gateway = JobPostingGateway

    def __init__(self):
        super().__init__()
        self.classifier = dspy.ChainOfThought(JobPostingSignature)

    def forward(self, message: str, author: str, channel_name: str) -> dspy.Prediction:
        return self.classifier(message=message, author=author, channel_name=channel_name,)
```

Then the only thing I need around this is the Discord network code. It's like 8 real lines of code for an LLM pipeline, plumbing included. The LLM logic is simple—to actually wire it up to Discord, I need a gateway.

## Building the gateway

The most complex part is integrating with Discord and implementing the business logic for taking actions based on the LLM outputs.

There are two main ways that we can build this bot:
1. Realtime streaming
2. Running on a cronjob

We opt for (2) the cron approach. Mostly because the realtime streaming requires us to maintain a websocket connection. If the dspy server was so popular that we had a large volume of messages, I might take on the higher complexity of building that. The dspy server averages way less than 20 messages every 5 minutes. 

If we instead just build something that checks the last 20 messages every 5 minutes, it's totally fine. If a job posting is live on the server for 5 minutes, no one cares. This constraint would be different for different servers, but these are the constraints of the problem I'm solving without overengineering.

The behavior will be as follows:

Every 5 minutes
1. Gather the last 20 messages
2. Skip any that have already been processed
3. Classify as "move", "flag", "delete", or "allow"
4. Take the relevant action for "move", "flag", "delete", and send an audit message into the moderator only channel
- "move" moves the message into the #jobs channel, and sends a message to the user
- "flag" adds an emoji reaction and sends an audit message for the mods to review, 
- "delete", deletes the message, and sends a message to the user
- "allow" does nothing

To implement this, I use `dspy-cli` to handle the routing and scheduling.

### Intro to dspy-cli

[`dspy-cli`](https://github.com/cmpnd-ai/dspy-cli) is a command line tool to help you create, scaffold, and deploy dspy applications. You can serve a `dspy-cli` created project by running `dspy-cli serve`, and it will bring up a local endpoint for you that you can test against. It is also what created our initial project directory structure.

There are a few different kinds entry points you may want for any DSPy application. The two that `dspy-cli` currently supports are **API-based** and **cron-based**.

For this case, we want to gather a bunch of inputs every so often, and run batch inference over them, so `CronGateway` makes more sense. We will subclass it to implement the loading logic.

`CronGateway` is what you use when your trigger is periodic rather than based on a call. 

`CronGateway` is an ABC with two core methods:

1. **`get_pipeline_inputs`**: Fetches your data and returns a list of input dictionaries for the pipeline to process. Each dict contains the kwargs for your module's `forward()` method. You can also include a `_meta` key for data needed in `on_complete` but not by the pipeline itself (like message IDs or channel IDs).

2. **`on_complete`**: Runs after each successful pipeline execution. This is where you take action based on the LLM's output. It receives both the original inputs (including `_meta`) and the pipeline output.

There's also an optional `on_error` method for handling failures.

### JobPostingGateway

`JobPostingGateway` subclasses `CronGateway`. This is how you specify your data loading behavior. In our case, it loads the data and takes actions afterward.

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

## Deploying our app

We deploy this onto Fly.io. We want a single permanently running machine that triggers itself every 5 minutes.

You can trigger the first deploy using `fly launch`.

### Scaling Configuration

Fly automatically scales your workload to 2 machines and will pause if there is not enough external traffic. For this deployment, there will by definition be 0 API-based traffic, so we need to turn off auto-scaling while keeping a minimum of one machine running.


#### Setting the minimum

You can add a line to your `fly.toml` to get the pausing behavior we want:

```toml
auto_stop_machines = false
auto_start_machines = true
min_machines_running = 1
```

If our one machine goes down, we do want it to start another one. We don't want it to stop a machine because of no activity, so we turn off `auto_stop_machines`.

#### Setting the maximum

We also don't want more than one machine: (1) I don't want to pay for that, and (2) we haven't built in any deduplication mechanisms. If there are two machines running, they might both pick up the same messages.

You can set the number of machines to one and turn off `ha` (horizontal autoscaling).
```bash
fly scale count 1
fly deploy --ha=false
```

`fly scale` should remove one of the two default machines if you already ran `fly launch`. This was a bit finicky when I was setting it up, so you may also need to run `fly machine kill` to manually remove one.

### Production Considerations

"production" is a loose word here because of the small scale, but this is deployed live, and actively affecting DSPy discord users.

Because this is such a small project, there wasn't a great dev environment nor was it worth it to set up one. I sent messages into `#general` to test this. Before I enabled any actions that would actually remove messages, I set up a dry run mode that would analyze messages and send a dry run audit message into `#moderator-only`. I saw that it was correctly flagging the examples that I put in, and that was enough to turn off dry run mode.

One other consideration: while it would be annoying for people to get messages falsely moved for a case that isn't specified, it's not the end of the world. A fine developer workflow is to notice a new error case, adjust the bot, and redeploy. Any change does not need to be thoroughly tested, because the stakes are quite low so long as it doesn't delete the whole Discord server.

### Persistence

We create a file to store all of the IDs that we have processed. Losing this isn't a big deal—at most you're redoing 20 call. If you were to expand this system, you'd certainly want to change it.

`fly volumes create dspy_discord_data --size 1`

Then inside `fly.toml` we add:
```toml
[mounts]
  source = "dspy_discord_data"
  destination = "/data"
```

### Secrets

Then we need to set the secrets. 

You'll need a Discord bot token with access to read messages, send messages, and delete messages. You can get the bot token from [this tutorial](https://discord.com/developers/docs/quick-start/getting-started). To get the Channel ID, make sure your Discord client is in developer mode, then right click on the channel and select `Copy Channel ID`.

```bash
fly secrets set \
  DISCORD_BOT_TOKEN="<Your token>" \
  DISCORD_CHANNEL_IDS="<CHANNEL_1>, <CHANNEL_2>" \
  DISCORD_JOBS_CHANNEL_ID="<CHANNEL_ID>" \
  DISCORD_AUDIT_CHANNEL_ID="<CHANNEL_ID>" \
  OPENAI_API_KEY="<PASTE YOUR OPENAI KEY>"
```

You can set the `DRY_RUN` environment variable to `true` if you want to only send audit logs without taking actions, to verify it's working properly.

## Conclusion

### Learnings

Fly.io + [`dspy-cli`](https://github.com/cmpnd-ai/dspy-cli) make it REALLY easy to deploy hobbyist DSPy usecases. This example was the first problem that I had that I wanted to use it to solve.

### Cost
  
**Price**

This is shockingly cheap to run! The LLM inference is not expensive (using gpt-5-nano), and the server costs <$1 per month (thank you Firecracker VMs + Fly.io). I'm happy to eat this cost to keep the server healthier and save myself the work I would have done otherwise.

**Development Time**

This bot did not take me that long to implement. The 25 lines of DSPy did not take long. I spent much longer writing the blog post than I did coding the bot. Especially once I had the Discord token enabled, it was incredibly easy for Amp to wire up the rest. I implemented the Gateway system for `dspy-cli` at the same time, and I took more time on that because its an important abstraction to get right.

**Maintainance**

If I want to make a change, all I need to do is update the signature, and run `fly deploy` to update my machine. Or, if I wanted to add more modules, I can still use the same VM.

### Limitations

**Volume**
  
This can by design, only work on 20 messages per 5 minutes. The limiting factors will be your LLM inference calls, rather than the ability of the runner to manage the requests.

**Prompt Injection**
  
Someone might be able to sneak in a job posting via prompt injection.

In practice, this doesn't actually matter. People are good at tagging the mods if a message does sneak through. 
  
The bot has no tool access, and it's not like the signature prompt is secret. There are no tools to access other messages, or ability to perform destructive actions towards other users.

Notably, I do not allow for any other messages in the thread context to be seen by the model. Showing full conversations would open up a lot of weird prompt injection avenues that I don't want to deal with.

**Spam**  

Processing a single message at a time means that we miss people who send a job posting in multiple channels. 

Often what these bots do is drop a message into every channel in the server. Because each message is processed individually, we currently would take all of these and (without deduping) move them into #jobs.

I will add some very simple dedup behavior in a future update, but for now I am just going to leave it. The goal of this bot for now is to catch the 80% of the simple cases.

Immediately after I made this bot, there were some messages it did not move when it should have. It thought some scammy crypto job postings were actually people introducing themselves. As some people in the Discord pointed out (thanks @prashanth and @mchonedev), it's pretty obvious that anyone using the word "blockchain" in their post is likely not a legitimate user. DSPy is not a crypto server, and any thoughtful dev would hopefully know their audience.

---

If you want to join the DSPy Discord and see the bot in action, here's the invite: [https://discord.gg/f5DJ778ZnK](https://discord.gg/f5DJ778ZnK)

## Appendix

### DSPy Signature to prompt example

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
```
System prompt:
1. Inputs
2. Outputs
3. Task

User prompt:
1. Field name: value for field, value in inputs
2. Desired assistant output list
```

The exact prompt that gets sent to the LLM for our signature above is:
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
general

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

### Batch Processing

For higher throughput, `CronGateway` supports batch mode which processes all inputs in parallel using DSPy's `module.batch()`:

```python
class JobPostingGateway(CronGateway):
    schedule = "*/5 * * * *"
    use_batch = True      # Enable parallel processing
    num_threads = 4       # Number of concurrent threads (optional)
    max_errors = 10       # Stop batch if this many errors occur (optional)
```

With batch mode enabled, the scheduler will call your module's `batch()` method instead of running `forward()` sequentially. This is useful when you have many inputs and want to parallelize LLM calls. The `on_complete` callback still runs once per input after all batch results return.

### Full fly.toml

```toml
app = 'discord-mod'
primary_region = 'ewr'

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
  processes = ['app']

[[vm]]
  memory = '1gb'
  cpu_kind = 'shared'
  cpus = 1
  memory_mb = 1024

[mounts]
  source = "processed_data"
  destination = "/data"
```