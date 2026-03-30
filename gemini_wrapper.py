from google import genai
from google.genai import types
from configs.tokens import GeminiAPI, GeminiModel
import logging
import traceback
from mysql_helper import GeminiMySqlConnectionManager

logger = logging.getLogger("gemini")
logger.setLevel(logging.INFO)
INSTRUCTION = []
TMP_CONTEXT_FORMAT = '-|{author}| wrote: |{message}|'
mysqlconn = None

try:
    mysqlconn = GeminiMySqlConnectionManager(logger)
    #[types.Part(text=entry) for entry in GeminiAPIInstruction]
    mysqlconn.init_db()
    mysqlconn.init_tables()
    rows = mysqlconn.get_persistent_context()
    rows.append(f'USE THE NEXT BLOCK ONLY FOR CONTEXT, NEW RESPONSE SHOULD BE AS USUAL, WITHOUT ANY FORMATTING FROM THE NEXT BLOCK')
    rows.append(f'[CONTEXT OF PREVIOUS CONVERSATIONS IN FORMAT: "{TMP_CONTEXT_FORMAT}"]')
    rows.extend([TMP_CONTEXT_FORMAT.format(author=author, message=message, response=response) for author, message, response in mysqlconn.get_temporary_context()])
    
    if rows:
        INSTRUCTION = [types.Part(text=entry) for entry in rows]
except:
    logger.exception(f"Failed to init MySQL db and get the persistent instructions")
    raise

def save_temp_instruction(author, message, response):
    global mysqlconn
    mysqlconn.insert_temporary_context(author, message, response)
    logger.info(f"Appended new temporary instruction")

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
    except Exception:
        raise

async def generate_response(
    client: genai.Client.aio,
    context_text: str,
    user_info: str,
    user_input: str,
    *,
    image_urls: list[str] | None = None,
    image_bytes: list[bytes] | None = None,
    model: str = GeminiModel,
    max_output_tokens: int = 512,
    temperature: float = 0.6,
    top_p: float = 0.9,
) -> str:
    """
    Send a prompt to the AI and return generated content (text).
    """
    prompt = f'''
    {{
        "Context": {context_text},
        "User info": {user_info},
        "User message": "{user_input}"
    }}
    '''
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
                system_instruction=INSTRUCTION,
            ),
        )
        response_text = response.text.removeprefix('FRS Bot: ')
        save_temp_instruction(author=user_info, message=user_input, response=response_text)
        INSTRUCTION.append(types.Part(text=TMP_CONTEXT_FORMAT.format(author=user_info, message=user_input, response=response_text)))
        logger.info(f'Current instruction length: {len(INSTRUCTION)}')
        return response_text
    except Exception:
        raise

async def generate_response_stream(
    client: genai.Client.aio,
    context_text: str,
    user_info: str,
    user_input: str,
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
    global INSTRUCTION
    prompt = f'''
    {{
        "Context": {context_text},
        "User info": {user_info},
        "User message": "{user_input}"
    }}
    '''
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
                system_instruction=instruction,
            ),
        ):
            # Only handle partial text deltas
            if event.type == "response.output_text.delta":
                response_text += event.delta
                yield response_text
    except Exception as e:
        raise RuntimeError(f"Failed during streaming: {e}") from e