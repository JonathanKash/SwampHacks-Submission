# Why some edits have no direction in the pixels

Lineage decides direction by asking which of two images is the cheaper lossy function of the
other. That works when an edit destroys information: a crop cannot be undone, a JPEG re-save
cannot be undone, a caption covers pixels that must be invented to go back.

Some edits are symmetric. If image B differs from image A only inside one compact region, the
pixels alone support two stories equally well:

- an object was added to A to make B (A is the parent), or
- an object was removed from B to make A (B is the parent).

Both stories invent exactly one region. Generative fills make the second story cheap and
realistic, which is why "object removed" edits from an image model were being claimed backwards
with high confidence before we measured this on real Gemini edits.

What breaks the symmetry, and what we do about each:

| Signal | Direction it gives | Status |
|---|---|---|
| Caption-like content on one side (achromatic, both dark and bright, wide luminance spread) | that side is the copy: captions are added, rarely removed | measured, 30/30 on the benchmark, used |
| Compression history (JPEG quantization quality) | parents are usually saved at higher quality | shown as a hint, never decides |
| Noise consistency inside the changed region | a generated fill is smoother than its surroundings | shown as an AI-edit indicator, never decides |
| Content Credentials (C2PA) with a signed edit history | explicit | read and validated when present |
| A third version of the image | whichever story also explains the third version wins | the audit tree does this automatically |

When none of these are available, the verdict is **inconclusive**, with both costs printed, and no
parent is claimed. We think that is the only honest answer a pixel-based tool can give.
