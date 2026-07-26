export function Skeleton({ width = '100%', height = 20, style }: { width?: string | number; height?: number; style?: React.CSSProperties }) {
  return (
    <div style={{
      width, height, borderRadius: 8,
      background: 'linear-gradient(90deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.06) 100%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s ease-in-out infinite',
      ...style,
    }} />
  );
}

export function PageSkeleton() {
  return (
    <div style={{ padding: '2rem', maxWidth: 600, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Skeleton height={32} width="60%" />
      <Skeleton height={16} width="40%" />
      <Skeleton height={120} />
      <Skeleton height={48} />
      <Skeleton height={48} />
    </div>
  );
}
