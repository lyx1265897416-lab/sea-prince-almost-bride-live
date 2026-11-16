# Original-quality playback

The opening is served from its immutable final-master CDN URL. The local media/OPEN.mp4 fallback is byte-identical. No additional publishing-time resize or bitrate reduction is allowed. Buffering must never select a lower-quality file.

The original-media.json record contains the verified SHA-256, size and URL. Preserve the approved edit, audio and subtitles when updating the opening. Upload future final masters directly and update the CDN mapping; do not transcode them for hosting.

Live-generated clips retain the model output URL. This audit checks the prerecorded public assets and the player routing; it does not generate new paid live rounds.
