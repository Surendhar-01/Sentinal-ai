import React from 'react';

const PIPELINE_NODES = [0, 1, 2, 3, 4];
const LAYERS = [0, 1, 2, 3];
const STREAM_ROWS = [0, 1, 2, 3, 4];
const SLIDERS = [
  { height: 62, depth: 0 },
  { height: 38, depth: 26 },
  { height: 78, depth: -26 },
];
const GATE_BARS = [0, 1, 2, 3];

function Pipeline({ size }) {
  return (
    <div className="s3d-scene" style={{ width: size, height: size * 0.6 }}>
      <div className="s3d-bar s3d-pipeline-rail" />
      {PIPELINE_NODES.map((index) => (
        <span
          key={index}
          className="s3d-node"
          style={{
            left: `${8 + index * 21}%`,
            animationDelay: `${index * 0.35}s`,
            transform: `translate(-50%,-50%) rotateY(${index % 2 ? 42 : -42}deg)`,
          }}
        />
      ))}
    </div>
  );
}

function Layers({ size }) {
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-spin s3d-spin-cw">
        {LAYERS.map((index) => (
          <span
            key={index}
            className="s3d-plane s3d-plane-fill"
            style={{ transform: `translateZ(${(index - 1.5) * 17}px)` }}
          />
        ))}
      </div>
    </div>
  );
}

function Orbit({ size }) {
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-core" />
      {[
        { tilt: 74, spin: 9, dir: 'cw' },
        { tilt: 58, spin: 13, dir: 'ccw' },
        { tilt: 90, spin: 17, dir: 'cw' },
      ].map((ring, index) => (
        <div key={index} className="s3d-spin s3d-spin-ccw" style={{ animationDuration: `${ring.spin}s` }}>
          <div className="s3d-ring" style={{ transform: `rotateX(${ring.tilt}deg)` }}>
            <span className="s3d-satellite" style={{ animationDelay: `${index * 0.6}s` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Prism({ size }) {
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-spin s3d-spin-slow">
        {[0, 60, 120].map((angle) => (
          <span key={angle} className="s3d-plane" style={{ transform: `rotateX(${angle}deg)` }} />
        ))}
      </div>
      <div className="s3d-spin s3d-spin-ccw s3d-spin-fast">
        {[0, 90].map((angle) => (
          <span key={angle} className="s3d-plane" style={{ transform: `rotateY(${angle}deg)` }} />
        ))}
      </div>
    </div>
  );
}

function Gate({ size }) {
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-gate-frame">
        {GATE_BARS.map((index) => (
          <span key={index} className={`s3d-gate-bar s3d-gate-bar-${index}`} />
        ))}
        <span className="s3d-gate-field" />
      </div>
    </div>
  );
}

function Stream({ size }) {
  return (
    <div className="s3d-scene" style={{ width: size, height: size * 0.8 }}>
      {STREAM_ROWS.map((index) => (
        <span
          key={index}
          className="s3d-stream-row"
          style={{
            top: `${12 + index * 19}%`,
            animationDelay: `${index * 0.4}s`,
            width: `${52 - index * 6}%`,
            transform: `translateZ(${(index - 2) * 14}px)`,
          }}
        />
      ))}
    </div>
  );
}

function Console({ size }) {
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-spin s3d-spin-slow">
        <span className="s3d-console-frame" />
        {SLIDERS.map((slider, index) => (
          <span
            key={index}
            className="s3d-console-track"
            style={{ left: `${26 + index * 24}%`, transform: `translate(-50%,0) translateZ(${slider.depth}px)` }}
          >
            <span className="s3d-console-knob" style={{ bottom: `${slider.height}%` }} />
          </span>
        ))}
      </div>
    </div>
  );
}

function Lattice({ size }) {
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-spin s3d-spin-slow">
        {[0, 1, 2, 3].map((row) =>
          [0, 1, 2, 3].map((col) => (
            <span
              key={`${row}-${col}`}
              className="s3d-lattice-cell"
              style={{
                left: `${4 + col * 24}%`,
                top: `${4 + row * 24}%`,
                transform: `translate(-50%,-50%) translateZ(${(col - 1.5) * 11 - (row - 1.5) * 7}px)`,
              }}
            />
          ))
        )}
      </div>
    </div>
  );
}

function Helix({ size }) {
  const rungs = [0, 1, 2, 3, 4, 5, 6, 7];
  return (
    <div className="s3d-box" style={{ width: size, height: size }}>
      <div className="s3d-spin s3d-spin-cw">
        {rungs.map((index) => {
          const top = 9 + index * 11;
          const angle = index * 42;
          return (
            <React.Fragment key={index}>
              <span
                className="s3d-helix-dot"
                style={{
                  top: `${top}%`,
                  transform: `translate(-50%,-50%) rotateY(${angle}deg) translateZ(${size * 0.3}px)`,
                }}
              />
              <span
                className="s3d-helix-dot s3d-helix-dot-alt"
                style={{
                  top: `${top}%`,
                  transform: `translate(-50%,-50%) rotateY(${angle + 180}deg) translateZ(${size * 0.3}px)`,
                }}
              />
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

const SCENES = {
  lattice: Lattice,
  pipeline: Pipeline,
  layers: Layers,
  orbit: Orbit,
  stream: Stream,
  prism: Prism,
  gate: Gate,
  helix: Helix,
  console: Console,
};

export default function Scene3D({ kind, size = 76, label }) {
  const Scene = SCENES[kind];
  if (!Scene) return null;
  return (
    <div
      className={`s3d s3d-${kind}`}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : 'true'}
    >
      <Scene size={size} />
    </div>
  );
}
