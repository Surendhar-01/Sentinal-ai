const MERIDIANS = [0, 30, 60, 90, 120, 150];
const PARALLELS = [-60, -30, 0, 30, 60];
const NODES = [
  [18, 32],
  [140, -22],
  [-48, 12],
  [96, 54],
  [-112, -38],
  [62, -8],
];

export default function Globe3D({ size = 260, label }) {
  const radius = size / 2;
  return (
    <div
      className="globe3d"
      style={{ width: size, height: size }}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : 'true'}
    >
      <div className="globe3d-scene">
        <div className="globe3d-core" />
        <div className="globe3d-shell" />
        {MERIDIANS.map((angle) => (
          <span key={`m${angle}`} className="globe3d-meridian" style={{ transform: `rotateY(${angle}deg)` }} />
        ))}
        {PARALLELS.map((angle) => (
          <span key={`p${angle}`} className="globe3d-parallel" style={{ transform: `rotateX(${angle}deg)` }} />
        ))}
        <div className="globe3d-orbit" />
        {NODES.map(([x, y], index) => (
          <span
            key={`n${index}`}
            className="globe3d-node"
            style={{
              transform: `rotateX(${y}deg) rotateY(${x}deg) translateZ(${radius}px)`,
              animationDelay: `${index * 0.4}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
