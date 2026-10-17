# How verification and provenance tools present findings (vocabulary, evidence drawers, reports)

_Research note produced with Google Gemini via the Antigravity CLI on 2026-10-17 at the team's request; reviewed and applied by the team. Claims marked 'from memory' by the model were not independently verified._

Here is the UX research and framework for **Lineage**, synthesized from verification platforms ([C2PA Content Credentials](https://contentcredentials.org/verify), [InVID-WeVerify](https://www.invid-project.eu/tools-and-services/invid-verification-plugin/), [Google "About this image"](https://blog.google/products/search/about-this-image-google-search/), [TinEye](https://tineye.com), [Relativity](https://www.relativity.com), Forensically *(from memory)*, and Truepic *(from memory)*).

---

### 1. Five UI/UX Conventions Auditors Expect

1. **Horizontal Chronological DAG with "Earliest Observed" Anchor**
   * **Element & Placement**: Main canvas. A directed acyclic graph oriented left-to-right (time flow), modeled on [Relativity's Email Thread Visualization](https://www.relativity.com).
   * **Wording**: The leftmost node must read **`Earliest Observed Instance`** (or `Candidate Original`) with a UTC crawl/capture timestamp—never an absolute claim like `True Genesis`.
2. **Aligned "Blink/Diff" Overlay Switch**
   * **Element & Placement**: Sticky top bar in the side-by-side node comparison viewer, modeled on [TinEye's](https://tineye.com) "Switch" button and InVID’s "CheckGIF".
   * **Wording**: `[Side-by-Side]` | `[Diff Overlay]` | `[Blink Toggle (Spacebar)]`. The diff should highlight pixel residuals or added/deleted text tokens in contrasting color overlays.
3. **Slide-Out "Derivation Evidence" Drawer**
   * **Element & Placement**: Collapsible right-hand drawer (like [C2PA Verify's](https://contentcredentials.org/verify) "Ingredients" panel), invoked by clicking any edge between two versions.
   * **Wording**: Grouped headers:
     * `Classified Operation`: e.g., *Crop (14% area loss) + Resample*.
     * `Keypoint Matches`: *142 inliers (RANSAC residual < 1.2px)*.
     * `Coverage`: *Source: 98.2% → Derived: 84.1%*.
     * `Color Transfer Fit`: *Residual error ΔE = 0.04*.
4. **Near-Duplicate Clustering / Collapsible Spares**
   * **Element & Placement**: Inline node badges with expanders (e.g., `+4 format variants`), borrowed directly from Relativity’s duplicate-spare stacks.
   * **Wording**: Group byte-identical or trivial format conversions (e.g., PNG vs. WebP at identical resolution) under `Format Duplicates (No Content Delta)` to prevent tree clutter.
5. **Persistent Tamper-Evident Metadata Footprint**
   * **Element & Placement**: Bottom-screen audit bar or node inspector footer.
   * **Wording**: Monospace display showing `SHA-256`, `pHash`, `Dimensions`, `File Size`, and `EXIF Integrity: [Parsed / Stripped / Mismatched]`.

---

### 2. Three Traps to Avoid (Common Auditor Complaints)

1. **The Black-Box "Authenticity Score" (e.g., "87% Original")**: In journalism and legal review, single aggregate probability scores are legally indefensible and unpublishable. *Fix*: Show per-metric thresholds and empirical error rates.
2. **Dense, Non-Collapsible "Spaghetti" Graphs**: Tools that dump 50 variants into an unconstrained force-directed graph force users to pan endlessly. *Fix*: Collapse duplicates, use hierarchical tree layouts, and filter by minimum derivation confidence.
3. **Destructive Forensic Overlays Without Synchronized Zoom**: InVID and Forensically users often complain that forensic heatmaps (ELA, noise maps) display without locked, 1:1 synchronized pan/zoom against the source image, leading to false-positive interpretations.

---

### 3. 'How to Read This' Explainer (Plain Language)

> **How to Read This Lineage Tree**  
> Each card represents a discovered version of this asset, ordered chronologically from left to right. Arrows show the path of modification: an arrow pointing from **Version A** to **Version B** means Version B was produced by editing Version A (such as cropping, color grading, or text alteration). The percentage displayed on each connection is the **Empirical Precision**—the statistical reliability of this specific edit classification, calculated against benchmarked test cases sharing similar evidence metrics. Clicking any connection opens the mathematical proof, including aligned visual overlays, pixel coverage, and matching keypoints. The leftmost asset is the **earliest observed source**, but unindexed earlier versions may still exist outside this dataset.

---

### 4. Recommended Vocabulary

| Concept | Options Considered | Recommended Term | Rationale |
| :--- | :--- | :--- | :--- |
| **Origin Asset** | `Root` vs. `Original` vs. `Candidate Original` | **`Candidate Original`** (or **`Earliest Observed`**) | In OSINT and e-discovery, an open-world assumption holds: you cannot prove an asset is the absolute camera root, only that it is the earliest in your corpus. "Root" sounds too abstract/computational. |
| **Relationship** | `Parent/Child` vs. `Derived From` | **`Source` → `Derived Copy`** (Edge label: **`Derived via [Action]`**) | Follows C2PA standards (`ingredient` / `derived from`). "Parent/child" is engineering slang and carries confusing hierarchical connotations. |
| **Certainty Metric**| `Confidence` vs. `Probability` vs. `Empirical Precision` | **`Empirical Precision`** (with tier labels: **`High / Moderate / Low Reliability`**) | "Confidence" is routinely confused with Bayesian belief or arbitrary AI hunches. "Empirical Precision" explicitly denotes real-world benchmark performance (e.g., *96% precision at 120+ inliers*). |

---

### 5. Exportable Report Contents (Newsroom & Legal Ready)

* **Report Header**: Case/Incident ID, Analyst Name/ID, Verification Timestamp (UTC), and Tool Version with Model/Algorithm Hashes.
* **Corpus Inventory (Evidence Table)**:
  * Asset ID & Thumbnail.
  * Filenames, MIME types, and File Dimensions/Word Counts.
  * Cryptographic Hashes (`SHA-256`, `MD5`) and Perceptual Hashes (`pHash`).
  * Ingestion Source / URL / Custodian and First-Seen Timestamp.
* **Lineage Topology Summary**: High-resolution vector diagram of the reconstructed edit tree highlighting the `Candidate Original` and primary divergent branches.
* **Decision-by-Decision Proof Ledger**:
  * Step-by-step transition table: `Source Node` → `Target Node`.
  * Inferred Action (e.g., *Spliced insertion*, *Global gamma shift*, *Downscaled 50%*).
  * Supporting Metrics: Inlier count, bidirectional overlap %, residual error, cost margin.
  * Calibration metric: Empirical precision % and False Positive Rate (FPR) tier.
* **Visual Diff Plates (Exhibit Pages)**: Side-by-side aligned comparisons, keypoint-spider match overlays, and residual difference heatmaps for contested transitions.
* **Methodology & Limitations Disclosure**: Standardized disclaimer detailing corpus bounds, unobserved intermediate ancestor risks, and algorithm calibration parameters.
