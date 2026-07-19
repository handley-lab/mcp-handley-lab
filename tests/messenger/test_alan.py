from mcp_handley_lab.messenger import alan


def test_passive_address_is_deterministic():
    assert alan.passive_addr("whatsapp:447700900123") == alan.passive_addr(
        "whatsapp:447700900123"
    )
    assert alan.passive_addr("telegram:a:b") != alan.passive_addr("telegram:a/b")
    assert alan.passive_addr("telegram:a/b") != alan.passive_addr("telegram:a.b")


def test_query_follows_exact_prompt_through_grouped_turn(monkeypatch):
    sent = []
    batches = [
        [],
        [
            {
                "idx": 3,
                "id": "claude-1#3",
                "payload": {
                    "kind": "prompt",
                    "text": "hello",
                    "external_id": "tg-7",
                },
            },
            {
                "idx": 4,
                "id": "claude-1#4",
                "payload": {
                    "kind": "native_turn",
                    "possible_causes": ["claude-1#2", "claude-1#3"],
                },
            },
            {
                "idx": 5,
                "id": "claude-1#5",
                "parent": "claude-1#4",
                "payload": {"kind": "claude_text", "text": "reply"},
            },
        ]
    ]
    monkeypatch.setattr(alan.loop, "tail_end", lambda _addr: 2)
    monkeypatch.setattr(alan.loop, "send", lambda *args, **kwargs: sent.append((args, kwargs)))
    monkeypatch.setattr(alan.loop, "tail", lambda *args, **kwargs: batches.pop(0))

    assert alan.query("claude-1", "messenger.telegram.-1", "hello", "tg-7") == "reply"
    assert sent == [
        (
            (
                "claude-1",
                {"kind": "prompt", "text": "hello", "external_id": "tg-7"},
            ),
            {
                "from_addr": "messenger.telegram.-1",
                "recognized_by": "messenger",
            },
        )
    ]


def test_ensure_claude_resumes_saved_actor(monkeypatch):
    spawned = []
    monkeypatch.setattr(alan.loop, "list", lambda: [])
    monkeypatch.setattr(alan.loop, "spawn", lambda addr: spawned.append(addr))
    assert alan.ensure_claude("claude-deadbeef", "messages", "/srv/messages") == (
        "claude-deadbeef"
    )
    assert spawned == ["claude-deadbeef"]


def test_ensure_claude_replaces_missing_saved_actor(monkeypatch):
    monkeypatch.setattr(alan.loop, "list", lambda: [])
    monkeypatch.setattr(
        alan.loop, "spawn", lambda _addr: (_ for _ in ()).throw(alan.loop.LoopError("unknown_source"))
    )
    monkeypatch.setattr(alan.loop, "spawn_claude", lambda _label, _cwd: "claude-new")
    assert alan.ensure_claude("claude-missing", "messages", "/srv/messages") == "claude-new"
