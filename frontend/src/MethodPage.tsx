import { Link } from "react-router-dom";
import NavBar from "./NavBar";
import NumbersPanel from "./NumbersPanel";
import { usePageTitle } from "./usePageTitle";

const TERMS: Array<{ name: string; weight: string; measures: string; direction: string }> = [
  {
    name: "coverage",
    weight: "3.0",
    measures: "After aligning the source onto the copy with ORB keypoints and a RANSAC homography, the fraction of the copy that the warped source does not cover. Registration uses 4000 ORB features and falls back to SIFT when ORB finds too few corners (small or soft images).",
    direction: "A crop or rotation is fully covered by its source; the source is not covered by the crop. The main direction signal.",
  },
  {
    name: "color residual",
    weight: "1.0",
    measures: "Mean squared error after fitting a per-channel affine color transform (gain and bias, matched by mean and spread) from the warped source to the copy.",
    direction: "Mostly symmetric: it says whether these are really the same picture. Brightness, contrast and tints are explained in either direction.",
  },
  {
    name: "blockiness",
    weight: "1.0",
    measures: "8×8 JPEG grid energy the copy has lost compared with the source, with a dead zone for noise. Only counted when the geometry is unchanged.",
    direction: "A copy cannot un-JPEG its source. Resampling destroys the grid legitimately, hence the geometry gate.",
  },
  {
    name: "resolution",
    weight: "0.5",
    measures: "Log ratio of pixel counts when the copy has more pixels than the source.",
    direction: "Information only flows down: a copy does not gain real resolution.",
  },
  {
    name: "chroma",
    weight: "2.0",
    measures: "Colorfulness the copy has that a grayscale source lacks, only when the color fit cannot explain it (a uniform tint of a gray image is explainable).",
    direction: "Color cannot be recreated from gray.",
  },
  {
    name: "entropy",
    weight: "0.5",
    measures: "Histogram entropy (bits) the copy has gained, only when a pure brightness/contrast/tint edit was detected (no geometry change, no JPEG, not grayscale).",
    direction: "Scaling with rounding and clipping can only lose entropy; JPEG ringing and interpolation would add some, hence the gates.",
  },
  {
    name: "blobs",
    weight: "20.0",
    measures: "Fraction of the overlap inside compact high-residual regions where the source has more edge energy than the copy: detail that was erased.",
    direction: "Adding a caption is cheap; removing one is expensive. A caption present only in the copy is not penalised.",
  },
  {
    name: "caption removed",
    weight: "1.0",
    measures: "The source carries text-like content (achromatic, both dark and bright, wide luminance spread) in the region where the two images differ, and the copy does not. Measured in each image's own frame on the strong-residual mask.",
    direction: "Captions are added far more often than removed, so the direction that removes one pays a flat penalty. On the benchmark the caption side was the derived copy 30 of 30 times.",
  },
  {
    name: "edit ops",
    weight: "0.05 each",
    measures: "A minimum-description-length prior: one small constant per detected edit primitive (crop, rotate, color, grayscale, JPEG, caption).",
    direction: "A copy is one edit from its source but two from its grandparent. When residuals tie, the shorter explanation wins; this keeps chains in order.",
  },
  {
    name: "specificity",
    weight: "0.01",
    measures: "Tiny tie-breaker toward the candidate with the least surplus pixels or compression headroom.",
    direction: "Among equally good explanations prefer the most specific ancestor.",
  },
  {
    name: "semantic fallback",
    weight: "2.0 + 5.0 × (1 − cos)",
    measures: "When registration fails (fewer than 12 consistent keypoints, or an implausible homography): CLIP cosine distance between the two images.",
    direction: "Always costs more than a good registration, so an AI restyle attaches by meaning but never outranks a pixel-aligned parent.",
  },
];

const DECISIVE_CUES: Array<{ name: string; direction: string }> = [
  { name: "coverage", direction: "less scene area points to the copy" },
  { name: "colour fit", direction: "the direction with the smaller post-fit residual is cheaper" },
  { name: "blockiness", direction: "extra JPEG grid loss points to the copy" },
  { name: "resolution", direction: "fewer real pixels points to the copy" },
  { name: "chroma", direction: "colour can become gray; gray cannot recover colour" },
  { name: "entropy", direction: "rounding and clipping lose entropy; they do not recreate it" },
  { name: "compact content difference", direction: "erased source detail costs more than added copy detail" },
  { name: "caption removed", direction: "caption-like content points toward the captioned copy" },
  { name: "number of edit operations", direction: "the direction needing fewer edit primitives wins" },
];

const INFORMATIVE_CUES = [
  "compression history (JPEG quality)",
  "stored dimensions",
  "EXIF",
  "Content Credentials",
  "noise consistency",
  "semantic similarity",
];

/** The method, in one page, for judges and industry readers. */
export default function MethodPage() {
  usePageTitle("Method · Lineage");
  return (
    <main className="landing method">
      <NavBar />
      <section className="hero text-hero">
        <p className="eyebrow">Method</p>
        <h1>How a parent is decided, term by term.</h1>
        <p className="lede">
          Everything below runs on pixels alone. The server stores who really made what only to score the
          demo; the engine never reads it. Weights live in one dictionary in <code>backend/lineage/config.py</code>.
        </p>
      </section>

      <section className="pipeline">
        <p className="eyebrow">Pipeline</p>
        <h2>Fingerprint, cost, arborescence.</h2>
        <ol className="stages">
          <li>
            <span className="stage-number">1</span>
            <h3>Candidates</h3>
            <p>
              Each image gets a 64-bit perceptual hash (DCT of a 32×32 thumbnail) and a 512-bit sign-binarised
              CLIP ViT-B/32 embedding. Hamming distance picks the 8 nearest relatives per image, so costs are
              computed for about 16 directed pairs per image instead of all n² pairs. The true parent was inside
              the top 8 in 98.9% of evaluated cases.
            </p>
          </li>
          <li>
            <span className="stage-number">2</span>
            <h3>Asymmetric cost</h3>
            <p>
              For a directed pair (a → b), align a onto b and charge for everything b has that a cannot supply.
              Every term only ever penalises the direction in which b would have gained information, because
              gaining information is what an edit cannot do.
            </p>
          </li>
          <li>
            <span className="stage-number">3</span>
            <h3>Minimum spanning arborescence</h3>
            <p>
              Chu-Liu/Edmonds, written from scratch and cross-checked against networkx in the tests, picks one
              incoming edge per image so the total cost is minimal and the result is a set of trees. A virtual
              root with a fixed cost (3.5) lets unrelated images become separate families instead of being
              glued to a bad parent.
            </p>
          </li>
        </ol>
      </section>

      <section className="pipeline">
        <p className="eyebrow">Evaluation</p>
        <h2>Numbers</h2>
        <NumbersPanel />
      </section>

      <section className="idea">
        <p className="eyebrow">Cost terms</p>
        <h2>What each term measures and why it points one way.</h2>
        <div className="method-table-wrap">
          <table className="method-table">
            <caption>Image cost terms, weights as deployed</caption>
            <thead>
              <tr>
                <th scope="col">term</th>
                <th scope="col">weight</th>
                <th scope="col">measures</th>
                <th scope="col">direction logic</th>
              </tr>
            </thead>
            <tbody>
              {TERMS.map((t) => (
                <tr key={t.name}>
                  <th scope="row">{t.name}</th>
                  <td>{t.weight}</td>
                  <td>{t.measures}</td>
                  <td>{t.direction}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="pipeline">
        <p className="eyebrow">Signal roles</p>
        <h2>What decides, what only informs</h2>
        <div className="idea-grid">
          <div className="idea-card">
            <span className="idea-arrow ok">decides</span>
            <ul className="method-list">
              {DECISIVE_CUES.map((cue) => (
                <li key={cue.name}>
                  <strong>{cue.name}</strong> — {cue.direction}
                </li>
              ))}
            </ul>
          </div>
          <div className="idea-card">
            <span className="idea-arrow">informs only</span>
            <ul className="method-list">
              {INFORMATIVE_CUES.map((cue) => <li key={cue}>{cue}</li>)}
            </ul>
          </div>
          <div className="idea-card">
            <span className="idea-arrow">Gates that stop a verdict</span>
            <ul className="method-list">
              <li>Re-rendered copy: the two align but the residual after the best colour fit is above 0.025 (genuine crops, filters and re-saves stay under 0.022; generative restyles measure 0.03 to 0.09). Direction cues no longer apply; reported as inconclusive with a measured AI-edit indicator.</li>
              <li>Single symmetric cue: a direction that rests only on a compact content difference (object added or removed) or only on the count of detected edit operations is not claimed.</li>
              <li>Margin below 0.02: the two directions are indistinguishable.</li>
            </ul>
          </div>
        </div>
        <p className="idea-note">
          Every verdict names the cues it rested on; a verdict that rests on a single symmetric cue is downgraded
          to inconclusive.
        </p>
      </section>

      <section className="pipeline">
        <p className="eyebrow">Evidence and confidence</p>
        <h2>Nothing is a guess.</h2>
        <div className="idea-grid">
          <div className="idea-card">
            <span className="idea-arrow ok">evidence</span>
            <p>
              Every decision ships with its measurements: keypoint inliers, coverage in both directions, the color
              fit, the cost of the reverse direction, the runner-up candidate and the margin between them. The
              visual diff plate shows the aligned source, the copy and the residual, so the numbers can be checked
              by eye.
            </p>
          </div>
          <div className="idea-card">
            <span className="idea-arrow ok">calibration</span>
            <p>
              We ran the pipeline over synthetic edit chains with known answers (three runs, six CC0 seeds, 276
              decisions) and recorded how often decisions with a given cost margin were right. That table is the
              only source of the precision figures shown in the app; text decisions show raw margins because the
              table was calibrated on images. We publish two numbers for every claim: the calibration on synthetic
              edit chains and the same bucket re-measured on real web memes. On 25 real generative edits these gates
              cut wrong-parent claims from 26% to 8%, at the price of abstaining 72% of the time. The lower one is the
              honest expectation for unknown files.
            </p>
          </div>
        </div>
        <p className="idea-note">
          Held-out accuracy on those runs: 71% and 81% (83% on the run used for tuning); roots found 6 of 6 every
          time. See the live table in <Link to="/">How sure is it?</Link>.
        </p>
      </section>

      <section className="idea">
        <p className="eyebrow">Limitations</p>
        <h2>Where it is honest about being unsure.</h2>
        <ul className="method-list">
          <li>A crop of a crop is also one crop from the grandparent; the edit-op prior resolves many of these, not all.</li>
          <li>A JPEG of a JPEG is also one JPEG from the clean original. Double-compression traces were tried (AC-coefficient sparsity) and rejected because they lowered held-out accuracy.</li>
          <li>
            Some edits have <a href="https://github.com/JonathanKash/SwampHacks-Submission/blob/main/docs/research/symmetry.md" target="_blank" rel="noopener">no direction in the pixels</a>. If two images differ only inside one compact region, 'object added' and 'object removed' are the same evidence. We return inconclusive unless a measured cue breaks the tie (caption-like content on one side, a signed Content Credentials history, or a third version of the image).
          </li>
          <li>A caption painted over an existing caption can attach to the sibling rather than the source.</li>
          <li>Two identical edits applied to the same source produce near-identical siblings that may attach to each other.</li>
          <li>The tree is built from the images supplied: "candidate original" means earliest within the corpus, and an earlier version outside it may exist.</li>
          <li>Metadata (EXIF, C2PA presence) is shown as a hint only: it is easy to strip or forge and never used as evidence.</li>
        </ul>
      </section>

      <section className="pipeline">
        <p className="eyebrow">Other media</p>
        <h2>The core does not know what an image is.</h2>
        <p className="idea-note">
          A media plug-in supplies four functions: load, fingerprint, cost and explain. The text plug-in uses
          SimHash and MinHash fingerprints, a cost in which words present in the copy but absent from the source
          are expensive (deleting is cheap, inventing is not), and explanations like "removed a sentence (18
          words)". <Link to="/text">Try it on text</Link>.
        </p>
      </section>

      <footer className="landing-footer">
        <p>
          Built at SwampHacks XII. Python, FastAPI, OpenCV (ORB, RANSAC), OpenCLIP, SQLite, React, D3. The code
          was written with AI coding agents under the team's direction; the approach, the cost design and the
          evaluation protocol are the team's. Full disclosure and credits in the README.
        </p>
      </footer>
    </main>
  );
}
