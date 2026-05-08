"""Tests for social_integrations module — Telegram + Instagram posting, preview, and publisher."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

from src.social_integrations.models import (
    PublishRequest,
    PublishResponse,
    PublishResult,
    PreviewRequest,
    PreviewResponse,
    Platform,
)
from src.social_integrations.telegram_poster import TelegramPoster
from src.social_integrations.instagram_poster import InstagramPoster
from src.social_integrations.publisher import SocialPublisher
from src.social_integrations.preview import PreviewGenerator


# ── Helpers ─────────────────────────────────────────────────


def _make_session_mock(json_response):
    """Create a mock aiohttp.ClientSession whose post returns the given JSON.

    Key: aiohttp.ClientSession.post() returns a _RequestContextManager (sync),
    not a coroutine. So the session must be a plain MagicMock, and only
    __aenter__ / __aexit__ / resp.json are AsyncMock.
    """
    # The response returned by ``async with session.post(...) as resp:``
    mock_resp = MagicMock()
    mock_resp.json = AsyncMock(return_value=json_response)

    # The context manager returned by session.post()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    # The session itself — plain MagicMock so .post() is sync
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post.return_value = mock_cm

    return mock_session


def _session_patch(session_mock):
    """Shortcut: patch aiohttp.ClientSession to return *session_mock*."""
    return patch("aiohttp.ClientSession", return_value=session_mock)


# ── TelegramPoster Tests ────────────────────────────────────


class TestTelegramPoster:
    """Tests for TelegramPoster.publish() — mock aiohttp.ClientSession."""

    @pytest.mark.asyncio
    async def test_no_token(self):
        """Empty bot_token → PublishResult(success=False)."""
        poster = TelegramPoster("")
        result = await poster.publish(chat_id="@test", text="Hello")
        assert result.success is False
        assert result.platform == "telegram"
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_text_too_long(self):
        """Text exceeding 4096 chars is truncated before sending."""
        poster = TelegramPoster("token")
        long_text = "A" * 5000
        mock_session = _make_session_mock({
            "ok": True,
            "result": {
                "message_id": 1,
                "chat": {"id": -100123, "username": "ch"},
                "date": 1715000000,
            },
        })
        with _session_patch(mock_session):
            result = await poster.publish(chat_id="@ch", text=long_text)
        assert result.success is True
        # The text sent should have been truncated to 4096 with trailing "..."
        call_args = mock_session.post.call_args
        sent_text = call_args[1]["json"]["text"]
        assert len(sent_text) == 4096
        assert sent_text.endswith("...")

    @pytest.mark.asyncio
    async def test_successful_text_post(self):
        """Valid text post → success with message_id and post_url."""
        poster = TelegramPoster("token")
        mock_session = _make_session_mock({
            "ok": True,
            "result": {
                "message_id": 456,
                "chat": {"id": -100123, "username": "mychannel"},
                "date": 1715000000,
            },
        })
        with _session_patch(mock_session):
            result = await poster.publish(chat_id="@mychannel", text="Hello world")
        assert result.success is True
        assert result.platform == "telegram"
        assert result.message_id == "456"
        assert result.post_url == "https://t.me/mychannel/456"

    @pytest.mark.asyncio
    async def test_successful_photo_post(self):
        """Post with image_url uses sendPhoto endpoint → success."""
        poster = TelegramPoster("token")
        mock_session = _make_session_mock({
            "ok": True,
            "result": {
                "message_id": 789,
                "chat": {"id": -100999, "username": "photoch"},
                "date": 1715000100,
            },
        })
        with _session_patch(mock_session):
            result = await poster.publish(
                chat_id="@photoch",
                text="Photo caption",
                image_url="https://img.example.com/pic.jpg",
            )
        assert result.success is True
        assert result.message_id == "789"
        assert result.post_url == "https://t.me/photoch/789"
        # Should have called sendPhoto, not sendMessage
        call_args = mock_session.post.call_args
        assert "sendPhoto" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_telegram_api_error(self):
        """Telegram returns ok=false → success=False with error description."""
        poster = TelegramPoster("token")
        mock_session = _make_session_mock({
            "ok": False,
            "description": "Bad Request: chat not found",
        })
        with _session_patch(mock_session):
            result = await poster.publish(chat_id="@badchat", text="Hello")
        assert result.success is False
        assert result.platform == "telegram"
        assert "Bad Request" in result.error

    @pytest.mark.asyncio
    async def test_http_error(self):
        """aiohttp.ClientError during post → success=False with HTTP error."""
        poster = TelegramPoster("token")
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_cm
        with _session_patch(mock_session):
            result = await poster.publish(chat_id="@test", text="Hello")
        assert result.success is False
        assert result.platform == "telegram"
        assert "HTTP error" in result.error
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        """Non-aiohttp exception → success=False with Unexpected."""
        poster = TelegramPoster("token")
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("Something exploded"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_cm
        with _session_patch(mock_session):
            result = await poster.publish(chat_id="@test", text="Hello")
        assert result.success is False
        assert result.platform == "telegram"
        assert "Unexpected" in result.error
        assert "Something exploded" in result.error


# ── InstagramPoster Tests ───────────────────────────────────


class TestInstagramPoster:
    """Tests for InstagramPoster.publish() — two-step Graph API flow."""

    @pytest.mark.asyncio
    async def test_no_credentials(self):
        """Missing access_token or account_id → success=False."""
        poster = InstagramPoster("", "")
        result = await poster.publish(caption="Test", image_url="https://img.com/p.jpg")
        assert result.success is False
        assert result.platform == "instagram"
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_successful_publish(self):
        """Full two-step flow: media creation + publish → success with media_id."""
        # Session 1: media creation
        s1 = _make_session_mock({"id": "178956"})
        # Session 2: publish
        s2 = _make_session_mock({"id": "179123"})

        poster = InstagramPoster("token", "act_123")
        with patch("aiohttp.ClientSession", side_effect=[s1, s2]), \
             patch("asyncio.sleep", AsyncMock()):
            result = await poster.publish(
                caption="Hello Instagram!",
                image_url="https://img.example.com/pic.jpg",
            )
        assert result.success is True
        assert result.platform == "instagram"
        assert result.message_id == "179123"
        assert result.post_url == "https://instagram.com/p/179123"

    @pytest.mark.asyncio
    async def test_media_creation_error(self):
        """First API call returns error → success=False, no second call."""
        s1 = _make_session_mock({"error": {"message": "Invalid image URL"}})
        # Second session should never be used
        s2 = MagicMock()

        poster = InstagramPoster("token", "act_123")
        with patch("aiohttp.ClientSession", side_effect=[s1, s2]), \
             patch("asyncio.sleep", AsyncMock()):
            result = await poster.publish(
                caption="Test",
                image_url="https://bad.url/pic.jpg",
            )
        assert result.success is False
        assert result.platform == "instagram"
        assert "Media creation" in result.error
        assert "Invalid image URL" in result.error
        # Second session should NOT have been called
        s2.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_creation_id(self):
        """Media creation returns no 'id' field → success=False."""
        s1 = _make_session_mock({})  # empty response, no "id"

        poster = InstagramPoster("token", "act_123")
        with patch("aiohttp.ClientSession", side_effect=[s1]), \
             patch("asyncio.sleep", AsyncMock()):
            result = await poster.publish(
                caption="Test",
                image_url="https://img.example.com/pic.jpg",
            )
        assert result.success is False
        assert result.platform == "instagram"
        assert "No creation_id" in result.error

    @pytest.mark.asyncio
    async def test_publish_error(self):
        """Media creation succeeds but publish step fails → success=False."""
        s1 = _make_session_mock({"id": "178956"})
        s2 = _make_session_mock({"error": {"message": "Publish rate limited"}})

        poster = InstagramPoster("token", "act_123")
        with patch("aiohttp.ClientSession", side_effect=[s1, s2]), \
             patch("asyncio.sleep", AsyncMock()):
            result = await poster.publish(
                caption="Test",
                image_url="https://img.example.com/pic.jpg",
            )
        assert result.success is False
        assert result.platform == "instagram"
        assert "Publish" in result.error
        assert "rate limited" in result.error


# ── SocialPublisher Tests ───────────────────────────────────


class TestSocialPublisher:
    """Tests for SocialPublisher.publish() — orchestrator with mock posters."""

    @pytest.mark.asyncio
    async def test_dry_run(self):
        """dry_run=True → returns preview, no posting, dry_run flag."""
        publisher = SocialPublisher()  # no posters configured
        req = PublishRequest(
            expert_id="exp-1",
            content="Hello world",
            platform=Platform.telegram,
            dry_run=True,
        )
        resp = await publisher.publish(req)
        assert resp.dry_run is True
        assert resp.preview is not None
        assert resp.preview["platform"] == "telegram"
        assert resp.results == []

    @pytest.mark.asyncio
    async def test_publish_to_telegram(self):
        """Non-dry-run telegram + mock poster → calls telegram poster."""
        mock_tg = AsyncMock()
        mock_tg.publish.return_value = PublishResult(
            platform="telegram", success=True, message_id="999"
        )
        publisher = SocialPublisher(telegram_poster=mock_tg)
        req = PublishRequest(
            expert_id="exp-1",
            content="Hello telegram",
            platform=Platform.telegram,
            channel_id="@mych",
        )
        resp = await publisher.publish(req)
        assert resp.dry_run is False
        assert len(resp.results) == 1
        assert resp.results[0].success is True
        assert resp.results[0].message_id == "999"
        mock_tg.publish.assert_called_once_with(
            chat_id="@mych",
            text="Hello telegram",
            image_url=None,
        )

    @pytest.mark.asyncio
    async def test_publish_to_instagram_no_image(self):
        """Instagram platform without image_url → returns error."""
        mock_ig = AsyncMock()
        publisher = SocialPublisher(instagram_poster=mock_ig)
        req = PublishRequest(
            expert_id="exp-1",
            content="Hello IG",
            platform=Platform.instagram,
            # no image_url
        )
        resp = await publisher.publish(req)
        assert resp.dry_run is False
        assert len(resp.results) == 1
        assert resp.results[0].success is False
        assert resp.results[0].platform == "instagram"
        assert "requires image_url" in resp.results[0].error
        mock_ig.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_to_instagram_with_image(self):
        """Instagram platform with image_url → calls instagram poster."""
        mock_ig = AsyncMock()
        mock_ig.publish.return_value = PublishResult(
            platform="instagram", success=True, message_id="ig-123"
        )
        publisher = SocialPublisher(instagram_poster=mock_ig)
        req = PublishRequest(
            expert_id="exp-1",
            content="Hello IG with pic",
            platform=Platform.instagram,
            image_url="https://img.example.com/pic.jpg",
        )
        resp = await publisher.publish(req)
        assert resp.dry_run is False
        assert len(resp.results) == 1
        assert resp.results[0].success is True
        assert resp.results[0].message_id == "ig-123"
        mock_ig.publish.assert_called_once_with(
            caption="Hello IG with pic",
            image_url="https://img.example.com/pic.jpg",
        )

    @pytest.mark.asyncio
    async def test_platform_not_configured(self):
        """Request for a platform with no poster → returns error."""
        publisher = SocialPublisher()  # no posters
        req = PublishRequest(
            expert_id="exp-1",
            content="Hello",
            platform=Platform.telegram,
        )
        resp = await publisher.publish(req)
        assert resp.dry_run is False
        assert len(resp.results) == 1
        assert resp.results[0].success is False
        assert "not configured" in resp.results[0].error


# ── PreviewGenerator Tests ──────────────────────────────────


class TestPreviewGenerator:
    """Tests for PreviewGenerator.generate() — pure function, no I/O."""

    def test_telegram_preview(self):
        """Telegram preview renders text, counts chars, returns warnings if URLs present."""
        gen = PreviewGenerator()
        req = PreviewRequest(content="Hello **world**", platform=Platform.telegram)
        resp = gen.generate(req)
        assert resp.platform == "telegram"
        assert "world" in resp.rendered_text
        assert resp.truncated is False
        assert resp.char_count > 0
        assert resp.line_count == 1
        assert isinstance(resp.estimated_read_time_sec, int)

    def test_telegram_exceeds_limit(self):
        """Text over max_length → truncated=True and warning."""
        gen = PreviewGenerator()
        long_text = "A" * 5000
        req = PreviewRequest(content=long_text, platform=Platform.telegram, max_length=4096)
        resp = gen.generate(req)
        assert resp.truncated is True
        assert len(resp.rendered_text) == 4096
        assert resp.rendered_text.endswith("...")
        assert any("truncated" in w.lower() for w in resp.warnings)

    def test_instagram_preview(self):
        """Instagram preview strips markdown, counts chars."""
        gen = PreviewGenerator()
        req = PreviewRequest(content="Hello **world**", platform=Platform.instagram)
        resp = gen.generate(req)
        assert resp.platform == "instagram"
        # Bold markers should have been stripped
        assert "**" not in resp.rendered_text
        assert "world" in resp.rendered_text
        assert resp.truncated is False
        assert resp.char_count > 0

    def test_instagram_hashtag_limit(self):
        """More than 30 unique hashtags → warning."""
        gen = PreviewGenerator()
        hashtags = " ".join(f"#tag{i}" for i in range(35))
        content = f"Check this out!\n{hashtags}"
        req = PreviewRequest(content=content, platform=Platform.instagram)
        resp = gen.generate(req)
        assert any("Too many hashtags" in w for w in resp.warnings)

    def test_instagram_first_line_short(self):
        """First line < 20 chars → warning about front-loading hook."""
        gen = PreviewGenerator()
        content = "Short\nMore content here on the second line"
        req = PreviewRequest(content=content, platform=Platform.instagram)
        resp = gen.generate(req)
        assert any("first line" in w.lower() or "short" in w.lower() for w in resp.warnings)
