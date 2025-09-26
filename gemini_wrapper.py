from google import genai
from google.genai import types
from configs.tokens import GeminiAPI, GeminiAPIInstruction, GeminiModel
import logging
import traceback

logger = logging.getLogger("gemini")
logger.setLevel(logging.INFO)

async def get_client(
        api_version: str | None = None
) -> genai.Client.aio:
    api_key = GeminiAPI
    client_kwargs = {
        "api_key": api_key
    }
    if api_version is not None:
        client_kwargs["http_options"] = types.HttpOptions(api_version=api_version)
    
    try:
        client = genai.Client(**client_kwargs)
        return client.aio
    except Exception as e:
        raise RuntimeError(f"Failed to initialize GenAI client: {e}") from e

async def generate_response(
    client: genai.Client.aio,
    prompt: str,
    *,
    image_urls: list[str] | None = None,
    image_bytes: list[bytes] | None = None,
    model: str = GeminiModel,
    max_output_tokens: int = 256,
    temperature: float = 0.6,
    top_p: float = 0.9,
) -> str:
    """
    Send a prompt to the AI and return generated content (text).
    """
    contents = [types.Part.from_text(text=prompt)]
    
    if image_urls:
        raise NotImplementedError("Images are not supported yet")
        for url in image_urls:
            try:
                contents.append(types.Part.from_image(url))
            except Exception as e:
                # Log invalid image URLs but continue
                logger.warning(f"Could not add image {url} to prompt: {e}")
    
    if image_bytes:
        raise NotImplementedError("Images are not supported yet")
        for img_bytes in image_bytes:
            try:
                contents.append(types.Part.from_image(img_bytes))
            except Exception as e:
                logger.warning(f"Could not add image bytes: {e}\n{traceback.format_exc()}")

    try:
        response = await client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                system_instruction=GeminiAPIInstruction,
            ),
        )
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to generate response: {e}") from e

async def generate_response_stream(
    client: genai.Client.aio,
    prompt: str,
    *,
    image_urls: list[str] | None = None,
    model: str = "gemini-2.5-flash",
    max_output_tokens: int = 256,
    temperature: float = 0.6,
    top_p: float = 0.9,
):
    """
    Stream AI response with partial updates.
    Yields partial text as it is generated.
    """
    raise NotImplementedError("Not working with streaming")
    contents = [types.Part.from_text(text=prompt)]

    if image_urls:
        for url in image_urls:
            try:
                contents.append(types.Part.from_image(url))
            except Exception as e:
                logger.warning(f"Could not add image {url}: {e}")

    response_text = ""

    try:
        async for event in client.models.stream_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                system_instruction=GeminiAPIInstruction,
            ),
        ):
            # Only handle partial text deltas
            if event.type == "response.output_text.delta":
                response_text += event.delta
                yield response_text
    except Exception as e:
        raise RuntimeError(f"Failed during streaming: {e}") from e