from src.services.slack_intake import extract_direct_message


def _payload(**event):
    base = {
        "type": "message",
        "channel_type": "im",
        "user": "U1",
        "channel": "D1",
        "text": "こんにちは",
        "ts": "1.0",
    }
    return {
        "type": "event_callback",
        "event_id": "Ev1",
        "team_id": "T1",
        "event": {**base, **event},
    }


def test_direct_message_is_extracted():
    message = extract_direct_message(_payload())
    assert message is not None
    assert (message.event_id, message.team_id, message.user_id, message.channel_id) == (
        "Ev1",
        "T1",
        "U1",
        "D1",
    )
    assert message.text == "こんにちは"


def test_bot_messages_are_ignored():
    # KUROKO 自身の返答に反応して無限に返し続けないこと
    assert extract_direct_message(_payload(bot_id="B1")) is None


def test_edits_and_other_subtypes_are_ignored():
    assert extract_direct_message(_payload(subtype="message_changed")) is None


def test_channel_messages_are_ignored():
    # メンションへの対応はバックログ（TASKS B16a）
    assert extract_direct_message(_payload(channel_type="channel")) is None


def test_blank_text_is_ignored():
    assert extract_direct_message(_payload(text="  ")) is None
