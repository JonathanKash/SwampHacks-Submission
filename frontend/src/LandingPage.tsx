import { Link } from "react-router-dom";
import NavBar from "./NavBar";
import NumbersPanel from "./NumbersPanel";
import QrCode from "./QrCode";
import { usePageTitle } from "./usePageTitle";
import { useTreePolling } from "./useTreePolling";

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}%`;
}

/** The front door: what Lineage is, why it works, and how to join the live demo. */
export default function LandingPage() {
  usePageTitle("Lineage");

  const { tree } = useTreePolling(5_000);
  const nodes = tree?.nodes.length ?? 0;
  const roots = tree?.nodes.filter((node) => node.root).length ?? 0;

  return (
    <main className="landing">
      <NavBar />

      <section className="hero">
        <p className="eyebrow">SwampHacks XII · live demo</p>
        <h1>
          Every edited image has a family tree.
          <br />
          <span className="accent">Lineage rebuilds it.</span>
        </h1>
        <p className="lede">
          Hand it a pile of edited copies of a picture and it works out which one is the original, who was
          derived from whom, and what edit produced each child. No metadata, no timestamps, no file names.
          Just pixels.
        </p>
        <div className="hero-actions">
          <Link to="/identify" className="primary-button cta">
            Identify a meme
            <small>one photo from your phone</small>
          </Link>
          <Link to="/edit" className="primary-button cta">
            Make an edit
            <small>on the tablet, 30 seconds</small>
          </Link>
          <Link to="/tree" className="secondary-button cta">
            Watch the tree
            <small>big screen, updates live</small>
          </Link>
        </div>
        <dl className="live-stats" aria-label="Live demo statistics">
          <div>
            <dt>images in the pool</dt>
            <dd>{nodes}</dd>
          </div>
          <div>
            <dt>families found</dt>
            <dd>{roots}</dd>
          </div>
          <div>
            <dt>tree accuracy</dt>
            <dd>{pct(tree?.accuracy.pct)}</dd>
          </div>
        </dl>
        <p className="live-stats-note">Live numbers from the demo pool on this screen.</p>
      </section>

      <section className="idea">
        <p className="eyebrow">Why it works</p>
        <h2>Edits destroy information, and information only flows one way.</h2>
        <div className="idea-grid">
          <div className="idea-card">
            <span className="idea-arrow ok">cheap</span>
            <p>
              A crop is easy to explain from the full picture: <em>“the big one, minus the edges.”</em> A JPEG
              re-save is <em>“the sharp one, blurred into 8×8 blocks.”</em>
            </p>
          </div>
          <div className="idea-card">
            <span className="idea-arrow bad">expensive</span>
            <p>
              The reverse never works. You cannot explain the full picture from the crop: the edges are
              gone. You cannot un-blur the blocks. The missing information has to be invented.
            </p>
          </div>
        </div>
        <p className="idea-note">
          So for every pair of images we ask: <strong>how cheaply can B be made from A?</strong> The cheap
          direction is parent → child. Chain those answers together and the whole tree falls out.
        </p>
      </section>

      <section className="pipeline">
        <p className="eyebrow">Under the hood</p>
        <h2>Three stages, each one plain enough to explain in a sentence.</h2>
        <ol className="stages">
          <li>
            <span className="stage-number">1</span>
            <h3>Fingerprint</h3>
            <p>
              Each image gets a 64-bit perceptual hash and a 512-bit CLIP code. Hamming distance finds the
              8 most likely relatives, so we never compare everything with everything.
            </p>
          </li>
          <li>
            <span className="stage-number">2</span>
            <h3>Asymmetric cost</h3>
            <p>
              Align A onto B with ORB keypoints and a RANSAC homography, then charge for what B has that A
              cannot supply: uncovered area, unexplained color, lost JPEG grid, erased detail. When
              alignment fails (an AI restyle), fall back to meaning via CLIP.
            </p>
          </li>
          <li>
            <span className="stage-number">3</span>
            <h3>Minimum spanning arborescence</h3>
            <p>
              Chu-Liu/Edmonds picks one parent per image so the total cost is as small as possible. A
              virtual root lets unrelated pictures become separate trees.
            </p>
          </li>
        </ol>
        <p className="idea-note">
          None of these stages knows what an image is. Swap the plug-ins and the same core traces paragraphs
          instead (<Link to="/text">try it on text</Link>). Every cost term, weight and limitation is on the
          method page (<Link to="/method">read the method</Link>).
        </p>
      </section>

      <section className="calibration">
        <p className="eyebrow">How much to trust it</p>
        <h2>Confidence is measured, not guessed.</h2>
        <p className="calibration-intro">
          We ran the pipeline over synthetic edit chains with known answers and recorded how often decisions
          with a given cost margin were right. Every confidence figure in the app is one of these numbers.
        </p>
        <p className="calibration-honesty">
          <strong>We publish both numbers:</strong> one calibrated on synthetic edit chains and one measured on an
          independent corpus of real web images. For an unknown file, the lower result is the honest expectation.
        </p>
        <NumbersPanel compact />
      </section>

      <section className="demo-how">
        <p className="eyebrow">Try it right now</p>
        <h2>You edit. It measures. The screen keeps score.</h2>
        <div className="demo-steps">
          <div className="demo-card">
            <h3>On the tablet</h3>
            <p>
              Pick any image from the pool and apply <strong>one</strong> edit: crop, rotate, a color
              filter, a caption, a crunchy JPEG re-save, or an AI restyle.
            </p>
          </div>
          <div className="demo-card">
            <h3>Behind the scenes</h3>
            <p>
              The server remembers which image you started from, but the engine is never told. It has to
              work out the parent from pixels alone.
            </p>
          </div>
          <div className="demo-card">
            <h3>On the big screen</h3>
            <p>
              Your image drops into the tree within a couple of seconds. Green edge: the measured parent is
              your real one. Red edge: the measurements pointed elsewhere. Every edge shows its evidence and
              an empirical confidence from our evaluation runs.
            </p>
          </div>
        </div>
        <p className="compare-invite">
          Have two files? <Link to="/compare">Compare them</Link> and ask why one is the parent.
        </p>
        <div className="join-row">
          <QrCode size={120} label="scan on your phone to make an edit" />
        </div>
        <div className="legend" aria-label="How to read the tree">
          <span className="legend-item"><i className="swatch ok" /> correct parent</span>
          <span className="legend-item"><i className="swatch bad" /> wrong parent</span>
          <span className="legend-item"><i className="swatch dashed" /> matched by meaning (restyle)</span>
          <span className="legend-item"><i className="swatch new" /> newest image</span>
        </div>
      </section>

      <section className="industry-audit">
        <p className="eyebrow">Where it is useful</p>
        <h2>Provenance audit</h2>
        <p className="industry-intro">
          When many versions of one image arrive without a known ground truth, Lineage identifies the likely
          original, explains what changed in each copy, and reports confidence using calibrated empirical
          precision on every edge.
        </p>
        <div className="industry-grid">
          <article className="industry-card">
            <h3>Newsroom verification</h3>
            <p>Sort source images from crops, captions, re-saves, and other circulated variants.</p>
          </article>
          <article className="industry-card">
            <h3>Trust &amp; safety</h3>
            <p>Trace how a visual changed as it moved across reports, accounts, and moderation queues.</p>
          </article>
          <article className="industry-card">
            <h3>Legal discovery</h3>
            <p>Organize related exhibits and preserve an exportable explanation of each parent decision.</p>
          </article>
          <article className="industry-card">
            <h3>Digital asset management</h3>
            <p>Separate likely masters from derived files and surface uncertain relationships for review.</p>
          </article>
        </div>
        <Link to="/audit" className="primary-button industry-cta">
          Open the audit workspace
        </Link>
      </section>

      <section className="judges-strip" aria-labelledby="judges-title">
        <p className="eyebrow">For judges</p>
        <h2 id="judges-title">For judges</h2>
        <div className="judges-grid">
          <Link to="/method" className="industry-card judges-card">
            <span className="judges-card-eyebrow">How it works</span>
            <h3>Method</h3>
            <p>Every cost term, the arborescence, what decides vs informs.</p>
            <span className="judges-card-arrow" aria-hidden="true">→</span>
          </Link>
          <Link to="/method" className="industry-card judges-card">
            <span className="judges-card-eyebrow">Calibration</span>
            <h3>Numbers</h3>
            <p>Synthetic vs web-memes calibration, caption-side cue record.</p>
            <span className="judges-card-arrow" aria-hidden="true">→</span>
          </Link>
          <a
            href="https://github.com/JonathanKash/SwampHacks-Submission/blob/main/docs/research/symmetry.md"
            className="industry-card judges-card"
            target="_blank"
            rel="noopener"
          >
            <span className="judges-card-eyebrow">Research note</span>
            <h3>Why some edits have no direction</h3>
            <p>When the evidence is symmetric, direction cannot be recovered.</p>
            <span className="judges-card-arrow" aria-hidden="true">↗</span>
          </a>
          <a
            href="https://github.com/JonathanKash/SwampHacks-Submission"
            className="industry-card judges-card"
            target="_blank"
            rel="noopener"
          >
            <span className="judges-card-eyebrow">Repository</span>
            <h3>Source and AI disclosure</h3>
            <p>
              Claude wrote the code under our direction; Codex built most of the frontend; Gemini (via
              Antigravity) edited the benchmark images.
            </p>
            <span className="judges-card-arrow" aria-hidden="true">↗</span>
          </a>
        </div>
      </section>

      <footer className="landing-footer">
        <p>
          Built at SwampHacks XII (University of Florida, October 2026). Python, FastAPI, OpenCV, OpenCLIP,
          React, D3, Gemini. Seed images are CC0 works from The Met Open Access collection.
        </p>
        <p>
          AI disclosure: the code was written with Claude Code under the team's direction; the approach,
          cost design and evaluation protocol are ours. Details in the README.
        </p>
      </footer>
    </main>
  );
}
