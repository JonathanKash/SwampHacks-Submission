# Current Gemini image-editing models and SDK call (checked 2026-10-16)

_Research note produced with Google Gemini via the Antigravity CLI on 2026-10-17 at the team's request; reviewed and applied by the team. Claims marked 'from memory' by the model were not independently verified._

# Google Gemini API: Current Image Editing Capability Report
*Date of Verification: 2026-10-16 (Live verification via official Google documentation)*

---

### 1. Current Model IDs for Image-to-Image Editing

Google's Gemini API has unified image generation and editing under its native multimodal image architecture (branded as **Nano Banana**). Legacy standalone Imagen models (`imagen-3.0-...`) have been shut down and deprecated on `ai.google.dev` in favor of these native models.

| Model ID | Public Alias | Recommended Use Case |
| :--- | :--- | :--- |
| **`gemini-nano-banana-2.1`** | **Nano Banana 2.1** | **Primary recommended workhorse**. Optimized for speed, cost, text rendering, multi-reference editing, and style transfers across 1K, 2K, and 4K resolutions. |
| **`gemini-3.1-flash-image`** | Nano Banana 2 | Previous-generation high-efficiency workhorse; supports multi-turn editing and 4K output. |
| **`gemini-3-pro-image`** | Nano Banana Pro | Premium tier for complex visual reasoning, intricate detail preservation, and precision creative control. |

> [!NOTE]
> `gemini-3.1-flash-lite-image` (Nano Banana 2 Lite) exists for ultra-cheap, fast generation, but official documentation notes it is **not** optimized for multi-reference inputs or sequential image editing.

---

### 2. Package Name & Configuration

* **Pip Package:** `google-genai` (current official Google GenAI SDK; replaces legacy `google-generativeai`).
  ```bash
  pip install --upgrade google-genai
  ```
* **Environment Variable:** **`GEMINI_API_KEY`** (automatically detected when initializing `genai.Client()`).

---

### 3. API Invocation Pattern

Native image generation and editing use the **Interactions API** (`client.interactions.create`):

* **Passing Input Image Bytes:** Base64-encode the raw bytes and provide an input block with `type: "image"`, `data: <base64_str>`, and `mime_type: "image/png"` (or `image/jpeg`). Combine this with a `type: "text"` block containing the edit instruction.
* **Extracting Output Image Bytes:** The SDK exposes the generated image on `interaction.output_image.data` as a Base64 string. Decode it using `base64.b64decode()`. (Alternatively, traverse `interaction.steps` for content blocks of type `"image"`).

---

### 4. Quotas, Pricing & Free Tier Status

* **Free Tier:** **No free tier exists** for image generation/editing models. Invoking these models without an active billing account yields a `429 RESOURCE_EXHAUSTED` error (quota limit is 0). A paid tier (Pay-as-you-go / Tier 1+) is required.
* **Pricing Model:** Token-based output billing based on generated resolution:
  * **`gemini-nano-banana-2.1` / `gemini-3.1-flash-image`:**
    * **1K resolution** (1,120 output tokens): ~$0.034 – $0.067 per image.
    * **2K resolution** (1,680 output tokens): ~$0.050 – $0.101 per image.
    * **4K resolution** (2,520 output tokens): ~$0.076 – $0.150 per image.
  * **`gemini-3-pro-image`:** ~$0.134 per 1K/2K image, ~$0.24 per 4K image.
  * **Input Tokens:** Standard multimodal input rates apply (~$0.50 – $1.50 per 1M input tokens).
  * **Batch API:** 50% discount on asynchronous generation jobs (up to 24-hour SLA).
* **Rate Limits:** Enforced via RPM (Requests Per Minute), RPD (Requests Per Day), and IPM (Images Per Minute) based on your billing tier.

---

### 5. Documentation Sources

* [Google AI for Developers - Image Generation & Editing Guide](https://ai.google.dev/gemini-api/docs/image-generation)
* [Google AI Studio - Gemini API Pricing](https://ai.google.dev/pricing)

---

### 6. Complete Runnable Python Function

```python
import base64
import os
from google import genai


def restyle(image_bytes: bytes, prompt: str, mime_type: str = "image/png") -> bytes:
    """Restyles an input image using Google's Gemini API image-to-image editing.

    Args:
        image_bytes: Raw bytes of the input image.
        prompt: Restyling instruction (e.g. 'restyle this photo as a watercolor').
        mime_type: MIME type of the input image ('image/png', 'image/jpeg', etc.).

    Returns:
        bytes: Raw bytes of the resulting restyled image.
    """
    # Reads GEMINI_API_KEY from environment variables by default
    client = genai.Client()

    # Encode input image bytes to base64 string
    base64_encoded_input = base64.b64encode(image_bytes).decode("utf-8")

    # Call the Interactions API for image editing
    interaction = client.interactions.create(
        model="gemini-nano-banana-2.1",
        input=[
            {
                "type": "image",
                "data": base64_encoded_input,
                "mime_type": mime_type,
            },
            {
                "type": "text",
                "text": prompt,
            },
        ],
    )

    # 1. Primary extraction via direct convenience attribute
    if (
        hasattr(interaction, "output_image")
        and interaction.output_image
        and hasattr(interaction.output_image, "data")
        and interaction.output_image.data
    ):
        return base64.b64decode(interaction.output_image.data)

    # 2. Fallback extraction via interaction steps traversal
    if hasattr(interaction, "steps") and interaction.steps:
        for step in interaction.steps:
            if getattr(step, "type", "") == "model_output":
                for content_block in getattr(step, "content", []):
                    if (
                        getattr(content_block, "type", "") == "image"
                        and hasattr(content_block, "data")
                        and content_block.data
                    ):
                        return base64.b64decode(content_block.data)

    raise RuntimeError("API completed successfully, but no output image was returned.")


if __name__ == "__main__":
    # Example execution:
    # Ensure GEMINI_API_KEY is set: export GEMINI_API_KEY="your-api-key"
    input_file = "input.png"
    output_file = "watercolor_output.png"

    if os.path.exists(input_file):
        with open(input_file, "rb") as f:
            src_bytes = f.read()

        result_bytes = restyle(
            image_bytes=src_bytes,
            prompt="Restyle this photo as a vibrant watercolor painting with visible paper texture and loose brushstrokes.",
            mime_type="image/png",
        )

        with open(output_file, "wb") as f:
            f.write(result_bytes)
        print(f"Successfully saved restyled image to {output_file}")
    else:
        print(f"Place an image at '{input_file}' to test.")
```
