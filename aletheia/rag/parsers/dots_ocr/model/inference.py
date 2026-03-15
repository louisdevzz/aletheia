import requests
import time
from aletheia.rag.parsers.dots_ocr.utils.image_utils import PILimage_to_base64
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()


def inference_with_api(
    image,
    prompt,
    base_url=None,
    api_key=None,
    protocol="http",
    ip="localhost",
    port=8000,
    temperature=0.1,
    top_p=0.9,
    max_completion_tokens=32768,
    model_name="rednote-hilab/dots.ocr",
):

    # Always use Kimi configuration
    base_url = os.environ.get("KIMI_BASE_URL", "https://api.kimi.com/coding/v1")
    final_api_key = os.environ.get("KIMI_API_KEY")
    if not final_api_key:
        print("WARNING: KIMI_API_KEY not found in environment variables.")

    # Default model from env if not provided
    if model_name == "rednote-hilab/dots.ocr" and os.environ.get("KIMI_MODEL"):
        model_name = os.environ.get("KIMI_MODEL")

    print(f"    [Inference] 🔧 Using Kimi API @ {base_url}")

    client = OpenAI(api_key=final_api_key, base_url=base_url)

    # Plain text prompt for Kimi
    text_content = prompt

    messages = []
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": PILimage_to_base64(image)},
                },
                {"type": "text", "text": text_content},
            ],
        }
    )

    max_retries = 5
    base_delay = 10  # seconds

    try:
        for attempt in range(max_retries):
            try:
                print(
                    f"    [Inference] 📡 API request to {model_name} (attempt {attempt + 1}/{max_retries})..."
                )
                req_start = time.time()
                response = client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    max_completion_tokens=max_completion_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                req_time = time.time() - req_start
                print(f"    [Inference] 📨 Response received in {req_time:.1f}s")
                break  # Success
            except Exception as e:
                # Check for rate limit error (usually 429)
                if "429" in str(e) or "quota" in str(e).lower():
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        print(
                            f"    [Inference] ⏳ Rate limited (429). Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                print(f"    [Inference] ❌ API error: {type(e).__name__}: {e}")
                raise e  # Re-raise other errors or if retries exhausted

        response_content = response.choices[0].message.content

        # Clean up markdown formatting if present
        if response_content.startswith("```json"):
            response_content = response_content[7:]
        elif response_content.startswith("```"):
            response_content = response_content[3:]

        if response_content.endswith("```"):
            response_content = response_content[:-3]

        return response_content.strip()
    except requests.exceptions.RequestException as e:
        print(f"request error: {e}")
        return None
    except Exception as e:
        print(f"API error: {e}")
        return None
