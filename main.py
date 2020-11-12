import logging
import json
import os
import nio
import discord


def config_gen(config_file):
    config_dict = {
        "homeserver": "https://matrix.org",
        "room_id": "room:matrix.org",
        "username": "@name:matrix.org",
        "password": "my-secret-password",
        "channel_id": "channel",
        "token": "my-secret-token"
    }

    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            json.dump(config_dict, f, indent=4)
            print(f"Example configuration dumped to {config_file}")
            exit()

    with open(config_file, "r") as f:
        config = json.loads(f.read())

    return config


config = config_gen("config.json")

discord_client = discord.Client()

logging.basicConfig(level=logging.INFO)


@discord_client.event
async def on_ready():
    print(f"Logged in as {discord_client.user}")

    # Start Matrix bot
    await create_matrix_client()


@discord_client.event
async def on_message(message):
    # Don't respond to bots/webhooks
    if message.author.bot:
        return

    message_ = f"<{message.author}> {message.content}"

    if str(message.channel.id) == config["channel_id"]:
        await message_send(message_)


async def emote(message):
    # Extract emotes from message
    emote_list = []
    for item in message.split():
        if item[0] == item[-1] == ":":
            emote_list.append(item[1:-1])

    # Replace emotes with IDs
    for emote in emote_list:
        emote = discord.utils.get(discord_client.emojis, name=emote)
        if emote is not None:
            emote = str(emote)
            replace_emote = emote.split(":")[1]
            message = message.replace(f":{replace_emote}:", emote)

    return message


async def webhook_send(author, message):
    # Get Discord channel from channel ID
    channel = int(config["channel_id"])
    channel = discord_client.get_channel(channel)

    # Create webhook if it doesn't exist
    hook_name = "matrix_bridge"
    hooks = await channel.webhooks()
    hook = discord.utils.get(hooks, name=hook_name)
    if hook is None:
        hook = await channel.create_webhook(name=hook_name)

    # Replace emote names
    message = await emote(message)

    await hook.send(content=message, username=author)


async def create_matrix_client():
    homeserver = config["homeserver"]
    username = config["username"]
    password = config["password"]

    timeout = 30000

    global matrix_client

    matrix_client = nio.AsyncClient(homeserver, username)
    print(await matrix_client.login(password))

    # Sync once before adding callback to avoid acting on old messages
    await matrix_client.sync(timeout)

    matrix_client.add_event_callback(message_callback, nio.RoomMessageText)

    # Sync forever
    await matrix_client.sync_forever(timeout=timeout)

    await matrix_client.close()


async def message_send(message):
    await matrix_client.room_send(
        room_id=config["room_id"],
        message_type="m.room.message",
        content={
            "msgtype": "m.text",
            "body": message
        }
    )


async def message_callback(room, event):
    message = event.formatted_body or event.body
    if not message:
        return

    # Don't reply to ourselves
    if event.sender == matrix_client.user:
        return

    await webhook_send(event.sender, message)


def main():
    # Start Discord bot
    discord_client.run(config["token"])


if __name__ == "__main__":
    main()
