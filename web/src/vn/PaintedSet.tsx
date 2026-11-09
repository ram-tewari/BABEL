/**
 * Built-in painted backdrops: every scene has an atmosphere before (or without) generated art.
 * Simple layered SVG in NOCTURNE's night palette, one composition per kind of place.
 */
export function PaintedSet({ category, night }: { category: string; night: boolean }) {
  const sky = night ? ["#070a12", "#121a2c", "#1c2540"] : ["#3a4a63", "#6d7d96", "#b9a68c"];
  const glow = night ? "#ffcf8a" : "#fff1d6";
  const kind = SETS[category] ?? SETS.room;
  return (
    <svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="ps-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={sky[0]} />
          <stop offset=".6" stopColor={sky[1]} />
          <stop offset="1" stopColor={sky[2]} />
        </linearGradient>
        <radialGradient id="ps-glow">
          <stop offset="0" stopColor={glow} stopOpacity=".9" />
          <stop offset="1" stopColor={glow} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ps-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2a1d14" />
          <stop offset="1" stopColor="#0d0907" />
        </linearGradient>
      </defs>
      {kind(night, glow)}
    </svg>
  );
}

type Draw = (night: boolean, glow: string) => React.ReactNode;

const skyline = (y: number, color: string, seed: number) => {
  const parts = [];
  let x = 0;
  let k = seed;
  while (x < 1600) {
    k = (k * 9301 + 49297) % 233280;
    const w = 60 + (k % 90);
    const h = 120 + (k % 220);
    parts.push(<rect key={x} x={x} y={y - h} width={w} height={h + 300} fill={color} />);
    if (k % 3 === 0) parts.push(<polygon key={`r${x}`} points={`${x},${y - h} ${x + w / 2},${y - h - 40} ${x + w},${y - h}`} fill={color} />);
    x += w + 4;
  }
  return parts;
};

const windows = (n: number, glow: string, seed: number) =>
  Array.from({ length: n }, (_, i) => {
    const k = (seed * 31 + i * 97) % 1000;
    return <rect key={i} x={(k * 1.6) % 1600} y={420 + ((k * 7) % 260)} width="10" height="14" fill={glow} opacity={0.35 + (k % 5) / 10} />;
  });

const SETS: Record<string, Draw> = {
  street: (night, glow) => (
    <>
      <rect width="1600" height="900" fill="url(#ps-sky)" />
      {night && <circle cx="1240" cy="150" r="46" fill="#e9e2cf" opacity=".85" />}
      <g opacity=".55">{skyline(560, night ? "#141b2a" : "#4a5468", 7)}</g>
      <g>{skyline(700, night ? "#0b0f18" : "#2c3342", 13)}</g>
      {windows(46, glow, 3)}
      <rect y="700" width="1600" height="200" fill={night ? "#0a0d14" : "#3b3a3a"} />
      {[180, 620, 1060, 1480].map((x) => (
        <g key={x}>
          <rect x={x} y="470" width="8" height="240" fill="#0a0a0a" />
          <circle cx={x + 4} cy="470" r="70" fill="url(#ps-glow)" opacity={night ? 0.8 : 0.25} />
          <circle cx={x + 4} cy="470" r="9" fill={glow} />
        </g>
      ))}
    </>
  ),
  room: (night) => (
    <>
      <rect width="1600" height="900" fill={night ? "#16121a" : "#3b2f26"} />
      <rect x="980" y="160" width="360" height="400" fill={night ? "#0e1a30" : "#9fb3c7"} />
      <path d="M980 360h360M1160 160v400" stroke="#2b1d14" strokeWidth="14" />
      <rect x="970" y="150" width="380" height="420" fill="none" stroke="#2b1d14" strokeWidth="18" />
      {night && <circle cx="1270" cy="230" r="34" fill="#e9e2cf" opacity=".8" />}
      <rect y="640" width="1600" height="260" fill="url(#ps-floor)" />
      <rect x="160" y="520" width="420" height="24" fill="#2a1a10" />
      <rect x="180" y="544" width="16" height="140" fill="#1d120b" />
      <rect x="544" y="544" width="16" height="140" fill="#1d120b" />
      <circle cx="300" cy="500" r="120" fill="url(#ps-glow)" opacity={night ? 0.7 : 0.3} />
      <rect x="292" y="470" width="16" height="50" fill="#f3e6cf" />
    </>
  ),
  parlor: (night, glow) => (
    <>
      <rect width="1600" height="900" fill={night ? "#1a1116" : "#4a2f2a"} />
      {[200, 600, 1000, 1400].map((x) => (
        <rect key={x} x={x - 60} y="120" width="120" height="520" rx="60" fill={night ? "#0f1626" : "#c7b9a0"} opacity=".9" />
      ))}
      <circle cx="800" cy="120" r="200" fill="url(#ps-glow)" opacity=".55" />
      <rect y="640" width="1600" height="260" fill="#2a1414" />
      <rect y="640" width="1600" height="10" fill={glow} opacity=".25" />
    </>
  ),
  tavern: (_night, glow) => (
    <>
      <rect width="1600" height="900" fill="#2a1a10" />
      {[260, 800, 1340].map((x) => (
        <g key={x}>
          <line x1={x} y1="0" x2={x} y2="180" stroke="#1a0f08" strokeWidth="6" />
          <circle cx={x} cy="200" r="180" fill="url(#ps-glow)" opacity=".75" />
          <circle cx={x} cy="200" r="16" fill={glow} />
        </g>
      ))}
      <rect y="560" width="1600" height="60" fill="#3d2414" />
      <rect y="620" width="1600" height="280" fill="url(#ps-floor)" />
      {Array.from({ length: 14 }, (_, i) => (
        <rect key={i} x={60 + i * 110} y={500 - (i % 3) * 8} width="22" height="60" rx="4" fill="#5a3a1a" opacity=".8" />
      ))}
    </>
  ),
  office: (night) => (
    <>
      <rect width="1600" height="900" fill={night ? "#121822" : "#3a4048"} />
      {[150, 450, 1150, 1450].map((x) => (
        <rect key={x} x={x - 110} y="140" width="220" height="460" fill="#24180f" />
      ))}
      {[150, 450, 1150, 1450].flatMap((x) => [180, 260, 340, 420, 500].map((y) => <rect key={`${x}${y}`} x={x - 100} y={y} width="200" height="8" fill="#3a2516" />))}
      <circle cx="800" cy="460" r="200" fill="url(#ps-glow)" opacity=".45" />
      <rect y="640" width="1600" height="260" fill="url(#ps-floor)" />
    </>
  ),
  church: (night) => (
    <>
      <rect width="1600" height="900" fill={night ? "#0f1220" : "#3a3540"} />
      {[400, 800, 1200].map((x) => (
        <g key={x}>
          <path d={`M${x - 90} 620V260a90 110 0 0 1 180 0V620z`} fill={night ? "#1a2a4a" : "#8fa0c0"} />
          <path d={`M${x} 160v460M${x - 90} 380h180`} stroke="#141018" strokeWidth="10" />
        </g>
      ))}
      <circle cx="800" cy="300" r="320" fill="url(#ps-glow)" opacity=".25" />
      <rect y="640" width="1600" height="260" fill="#14101a" />
      {[300, 1300].map((x) => (
        <g key={x}>
          <circle cx={x} cy="600" r="60" fill="url(#ps-glow)" />
          <rect x={x - 6} y="600" width="12" height="40" fill="#f3e6cf" />
        </g>
      ))}
    </>
  ),
  forest: (night) => (
    <>
      <rect width="1600" height="900" fill="url(#ps-sky)" />
      {Array.from({ length: 22 }, (_, i) => {
        const x = (i * 83) % 1600;
        const h = 420 + ((i * 53) % 240);
        return <path key={i} d={`M${x} 900V${900 - h}l-70 140h50l-80 160h60l-90 180h260l-90-180h60l-80-160h50z`} fill={i % 2 ? (night ? "#0a1410" : "#24392c") : night ? "#0f1c16" : "#2f4a39"} />;
      })}
    </>
  ),
  countryside: (night) => (
    <>
      <rect width="1600" height="900" fill="url(#ps-sky)" />
      <path d="M0 620Q400 520 800 600T1600 580V900H0z" fill={night ? "#101a14" : "#56704a"} />
      <path d="M0 720Q500 640 1000 700T1600 690V900H0z" fill={night ? "#0b120e" : "#3f5636"} />
    </>
  ),
  harbor: (night, glow) => (
    <>
      <rect width="1600" height="900" fill="url(#ps-sky)" />
      <rect y="560" width="1600" height="340" fill={night ? "#08101c" : "#3f5a72"} />
      {[300, 900, 1300].map((x) => (
        <g key={x} fill={night ? "#05070b" : "#22252c"}>
          <rect x={x} y="300" width="10" height="290" />
          <path d={`M${x - 140} 560h300l-40 60h-220z`} />
        </g>
      ))}
      {windows(10, glow, 9)}
    </>
  ),
  ship: (night) => (
    <>
      <rect width="1600" height="900" fill="url(#ps-sky)" />
      <rect y="520" width="1600" height="380" fill={night ? "#07101c" : "#3d5e7c"} />
      <path d="M0 700h1600v200H0z" fill="#3a2414" />
      <rect x="760" y="120" width="18" height="580" fill="#2a1a0e" />
    </>
  ),
  mystic: (night) => (
    <>
      <rect width="1600" height="900" fill={night ? "#0c0d14" : "#3a3c48"} />
      <circle cx="800" cy="450" r="520" fill="#8a8fa8" opacity=".12" />
      <circle cx="800" cy="450" r="300" fill="#c8cbe0" opacity=".08" />
    </>
  ),
  underground: () => (
    <>
      <rect width="1600" height="900" fill="#0d0c0e" />
      <path d="M300 900V300a500 260 0 0 1 1000 0V900z" fill="#1c1a1e" />
      <path d="M500 900V380a300 160 0 0 1 600 0V900z" fill="#09080a" />
      {[420, 1180].map((x) => (
        <circle key={x} cx={x} cy="420" r="90" fill="url(#ps-glow)" opacity=".6" />
      ))}
    </>
  ),
};
SETS.shop = SETS.tavern;
SETS.library = SETS.office;
SETS.classroom = SETS.office;
SETS.hospital = SETS.room;
SETS.palace = SETS.parlor;
SETS.carriage = SETS.room;
SETS.train = SETS.room;
SETS.tent = SETS.tavern;
