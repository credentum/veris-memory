# Speech-to-Text (STT) and Text-to-Speech (TTS) Implementation Guide

## Overview

The voice-bot service currently has placeholder implementations for STT and TTS providers. This guide provides implementation notes for integrating various providers.

## Current Architecture

```
User Voice → LiveKit → Voice Bot → STT Provider → Text
Text → Voice Bot → TTS Provider → Audio → LiveKit → User
```

## Status

- ✅ **Infrastructure**: LiveKit integration complete
- ✅ **Memory**: Fact storage and retrieval working
- ⚠️ **STT**: Provider interface defined, implementations needed
- ⚠️ **TTS**: Provider interface defined, implementations needed

---

## Speech-to-Text (STT) Providers

### 1. Deepgram (Recommended - Fast & Accurate)

**Pros**:
- Low latency (<300ms)
- High accuracy
- WebSocket streaming support
- Good for real-time applications

**Implementation**:

```python
# voice-bot/app/stt/deepgram_provider.py
import asyncio
from deepgram import Deepgram
from typing import AsyncIterator

class DeepgramSTTProvider:
    def __init__(self, api_key: str):
        self.dg_client = Deepgram(api_key)

    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """
        Transcribe audio stream in real-time

        Args:
            audio_stream: Async iterator of audio bytes

        Yields:
            Transcribed text segments
        """
        try:
            source = {'buffer': audio_stream, 'mimetype': 'audio/linear16'}
            response = await self.dg_client.transcription.live({
                'punctuate': True,
                'interim_results': True,
                'language': 'en-US',
                'model': 'nova-2',
            })

            async for text in response:
                if text.get('is_final'):
                    transcript = text.get('channel', {}).get('alternatives', [{}])[0].get('transcript', '')
                    if transcript:
                        yield transcript

        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            raise

    async def transcribe_file(self, audio_data: bytes) -> str:
        """Transcribe complete audio file"""
        source = {'buffer': audio_data, 'mimetype': 'audio/wav'}
        response = await self.dg_client.transcription.prerecorded(source, {
            'punctuate': True,
            'language': 'en-US',
            'model': 'nova-2',
        })

        return response['results']['channels'][0]['alternatives'][0]['transcript']
```

**Configuration**:
```env
STT_PROVIDER=deepgram
STT_API_KEY=your_deepgram_api_key
```

**Dependencies**:
```txt
deepgram-sdk==3.4.0
```

**Cost**: ~$0.0043 per minute (Nova-2 model)

---

### 2. OpenAI Whisper

**Pros**:
- Excellent accuracy
- Multiple languages
- No streaming (batch processing)

**Implementation**:

```python
# voice-bot/app/stt/whisper_provider.py
import openai
import tempfile
import os
from typing import Optional

class WhisperSTTProvider:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    async def transcribe_file(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """
        Transcribe audio file using Whisper

        Args:
            audio_data: Audio bytes (WAV, MP3, etc.)
            language: Optional language code (e.g., 'en')

        Returns:
            Transcribed text
        """
        try:
            # Write to temporary file (Whisper API requires file)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name

            try:
                with open(tmp_path, 'rb') as audio_file:
                    transcript = await openai.Audio.atranscribe(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )
                    return transcript['text']
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            raise
```

**Configuration**:
```env
STT_PROVIDER=whisper
STT_API_KEY=sk-...
```

**Dependencies**:
```txt
openai==1.3.0
```

**Cost**: $0.006 per minute

**Note**: Not ideal for real-time streaming (batch only)

---

### 3. Google Cloud Speech-to-Text

**Pros**:
- Streaming support
- Good accuracy
- Multiple languages

**Implementation**:

```python
# voice-bot/app/stt/google_provider.py
from google.cloud import speech_v1p1beta1 as speech
from typing import AsyncIterator

class GoogleSTTProvider:
    def __init__(self, credentials_path: str):
        self.client = speech.SpeechClient.from_service_account_json(credentials_path)

    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe audio stream using Google STT"""
        config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code='en-US',
                enable_automatic_punctuation=True,
            ),
            interim_results=True,
        )

        async for response in self.client.streaming_recognize(config, audio_stream):
            for result in response.results:
                if result.is_final:
                    yield result.alternatives[0].transcript
```

**Configuration**:
```env
STT_PROVIDER=google
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

**Dependencies**:
```txt
google-cloud-speech==2.21.0
```

**Cost**: $0.006 per 15 seconds

---

## Text-to-Speech (TTS) Providers

### 1. ElevenLabs (Recommended - Natural Voice)

**Pros**:
- Most natural-sounding voices
- Low latency streaming
- Voice cloning support
- Multiple voices and styles

**Implementation**:

```python
# voice-bot/app/tts/elevenlabs_provider.py
import asyncio
from elevenlabs import generate, stream, Voice, VoiceSettings
from typing import AsyncIterator

class ElevenLabsTTSProvider:
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        self.api_key = api_key
        self.voice_id = voice_id  # Default: Rachel voice

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Generate speech audio stream

        Args:
            text: Text to convert to speech

        Yields:
            Audio bytes (MP3 chunks)
        """
        try:
            audio_stream = generate(
                text=text,
                voice=Voice(
                    voice_id=self.voice_id,
                    settings=VoiceSettings(
                        stability=0.5,
                        similarity_boost=0.75,
                        style=0.5,
                        use_speaker_boost=True
                    )
                ),
                model="eleven_turbo_v2",  # Fastest model
                stream=True,
                api_key=self.api_key
            )

            for chunk in audio_stream:
                yield chunk

        except Exception as e:
            logger.error(f"ElevenLabs synthesis error: {e}")
            raise

    async def synthesize_file(self, text: str) -> bytes:
        """Generate complete audio file"""
        audio = generate(
            text=text,
            voice=self.voice_id,
            model="eleven_turbo_v2",
            api_key=self.api_key
        )
        return audio
```

**Configuration**:
```env
TTS_PROVIDER=elevenlabs
TTS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Optional, default: Rachel
```

**Dependencies**:
```txt
elevenlabs==1.0.0
```

**Cost**: ~$0.30 per 1K characters (Turbo model)

**Available Voices**:
- Rachel: 21m00Tcm4TlvDq8ikWAM (female, American)
- Adam: pNInz6obpgDQGcFmaJgB (male, American)
- Domi: AZnzlk1XvdvUeBnXmlld (female, American)

---

### 2. Google Cloud Text-to-Speech

**Pros**:
- Reliable
- Multiple voices
- Good pricing

**Implementation**:

```python
# voice-bot/app/tts/google_provider.py
from google.cloud import texttospeech_v1 as texttospeech

class GoogleTTSProvider:
    def __init__(self, credentials_path: str):
        self.client = texttospeech.TextToSpeechClient.from_service_account_json(credentials_path)

    async def synthesize_file(self, text: str, voice_name: str = "en-US-Neural2-F") -> bytes:
        """Generate speech audio"""
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=voice_name,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0,
        )

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        return response.audio_content
```

**Configuration**:
```env
TTS_PROVIDER=google
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

**Dependencies**:
```txt
google-cloud-texttospeech==2.14.0
```

**Cost**: $4 per 1M characters (Neural2 voices)

---

### 3. Azure Cognitive Services TTS

**Pros**:
- Enterprise-grade
- Neural voices
- SSML support

**Implementation**:

```python
# voice-bot/app/tts/azure_provider.py
import azure.cognitiveservices.speech as speechsdk
from typing import AsyncIterator

class AzureTTSProvider:
    def __init__(self, subscription_key: str, region: str):
        self.speech_config = speechsdk.SpeechConfig(
            subscription=subscription_key,
            region=region
        )
        self.speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Generate speech audio stream"""
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config)

        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            yield result.audio_data
        else:
            logger.error(f"Azure TTS error: {result.reason}")
            raise Exception(f"Azure TTS failed: {result.reason}")
```

**Configuration**:
```env
TTS_PROVIDER=azure
AZURE_SPEECH_KEY=your_subscription_key
AZURE_SPEECH_REGION=eastus
```

**Dependencies**:
```txt
azure-cognitiveservices-speech==1.31.0
```

**Cost**: $15 per 1M characters (Neural voices)

---

## Integration with Voice Handler

### Update VoiceHandler

```python
# voice-bot/app/voice_handler.py
from app.stt.deepgram_provider import DeepgramSTTProvider
from app.tts.elevenlabs_provider import ElevenLabsTTSProvider

class VoiceHandler:
    def __init__(self, livekit_url: str, api_key: str, api_secret: str,
                 stt_provider: str, stt_api_key: str,
                 tts_provider: str, tts_api_key: str):
        # ... existing init code ...

        # Initialize STT provider
        if stt_provider == "deepgram":
            self.stt = DeepgramSTTProvider(stt_api_key)
        elif stt_provider == "whisper":
            self.stt = WhisperSTTProvider(stt_api_key)
        elif stt_provider == "google":
            self.stt = GoogleSTTProvider(stt_api_key)

        # Initialize TTS provider
        if tts_provider == "elevenlabs":
            self.tts = ElevenLabsTTSProvider(tts_api_key)
        elif tts_provider == "google":
            self.tts = GoogleTTSProvider(tts_api_key)
        elif tts_provider == "azure":
            self.tts = AzureTTSProvider(tts_api_key, azure_region)

    async def process_voice_input(self, audio_stream):
        """Process voice input through STT → Memory → TTS pipeline"""
        # 1. Transcribe audio
        async for text in self.stt.transcribe_stream(audio_stream):
            logger.info(f"Transcribed: {text}")

            # 2. Process with memory client
            response = await self.process_with_memory(text)

            # 3. Generate audio response
            async for audio_chunk in self.tts.synthesize_stream(response):
                yield audio_chunk
```

---

## Testing Strategy

### Unit Tests

```python
# voice-bot/tests/test_stt_provider.py
import pytest
from app.stt.deepgram_provider import DeepgramSTTProvider

@pytest.mark.asyncio
async def test_deepgram_transcription():
    """Test Deepgram transcription"""
    provider = DeepgramSTTProvider(api_key="test_key")

    # Mock audio data
    audio_data = b"..."  # Sample WAV file bytes

    result = await provider.transcribe_file(audio_data)

    assert isinstance(result, str)
    assert len(result) > 0
```

### Integration Tests

```bash
# Test with real audio file
curl -X POST http://localhost:8002/api/v1/voice/transcribe \
  -F "audio=@test_audio.wav"
```

---

## Recommended Implementation Order

1. **Phase 1**: Deepgram STT (streaming real-time)
2. **Phase 2**: ElevenLabs TTS (natural voice)
3. **Phase 3**: LiveKit audio pipeline integration
4. **Phase 4**: Add alternative providers (Whisper, Google)

---

## Performance Considerations

### Latency Targets

- **STT**: <300ms (real-time streaming)
- **TTS**: <200ms for first chunk
- **Total**: <500ms end-to-end

### Optimization Tips

1. **Use streaming** for STT/TTS when possible
2. **Cache TTS responses** for common phrases
3. **Pre-generate welcome messages**
4. **Use WebSocket** connections to reduce overhead
5. **Parallel processing**: Start TTS while still receiving STT

---

## Cost Estimates (1000 minutes of conversation)

| Provider | Type | Cost per 1K min | Total |
|----------|------|-----------------|-------|
| Deepgram | STT | $4.30 | $4.30 |
| ElevenLabs | TTS | ~$50* | $50.00 |
| LiveKit | Infrastructure | Free (self-hosted) | $0.00 |
| **Total** | | | **~$54.30** |

\* Based on average response length of ~100 words/response

---

## Security Considerations

1. **API Keys**: Store in environment variables, never in code
2. **Audio Data**: Don't log or persist user audio (GDPR/privacy)
3. **Rate Limiting**: Implement per-user rate limits
4. **Authentication**: Verify user identity before processing voice

---

## Next Steps

1. Install provider dependencies: `pip install -r requirements-voice.txt`
2. Choose STT/TTS providers based on requirements
3. Implement provider classes in `voice-bot/app/stt/` and `voice-bot/app/tts/`
4. Update `VoiceHandler` to use providers
5. Add integration tests
6. Update documentation with provider-specific setup

---

## Resources

- **Deepgram**: https://deepgram.com/docs
- **ElevenLabs**: https://elevenlabs.io/docs
- **OpenAI Whisper**: https://platform.openai.com/docs/guides/speech-to-text
- **Google Cloud**: https://cloud.google.com/speech-to-text
- **Azure**: https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/

---

## Support

For questions or issues:
1. Check provider documentation
2. Review voice-bot logs: `docker logs voice-bot`
3. Test with validation script: `./voice-bot/scripts/validate_sprint1.sh`
4. Check MCP server connectivity: `curl http://localhost:8000/health`
