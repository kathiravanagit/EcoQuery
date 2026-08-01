import React from 'react';

export function Skeleton({ width = '100%', height = 20, style }: { width?: string | number; height?: number; style?: React.CSSProperties }) {
  return (
    <div style={{
      width, height, borderRadius: 4,
      background: 'linear-gradient(90deg, var(--border-color) 0%, rgba(255,255,255,0.08) 50%, var(--border-color) 100%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s ease-in-out infinite',
      ...style,
    }} />
  );
}

export function PageSkeleton() {
  return (
    <div style={{ padding: '2rem', maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Skeleton height={32} width="50%" />
      <Skeleton height={14} width="70%" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
        <Skeleton height={120} />
        <Skeleton height={120} />
        <Skeleton height={120} />
        <Skeleton height={120} />
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div style={{ padding: '2rem', maxWidth: 1000, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Skeleton height={28} width="30%" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <Skeleton height={100} />
        <Skeleton height={100} />
        <Skeleton height={100} />
      </div>
      <Skeleton height={200} />
      <Skeleton height={150} />
    </div>
  );
}

export function BlogSkeleton() {
  return (
    <div style={{ padding: '2rem', maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Skeleton height={24} width="60%" />
      <Skeleton height={14} width="30%" />
      <Skeleton height={200} />
      <Skeleton height={14} width="100%" />
      <Skeleton height={14} width="90%" />
      <Skeleton height={14} width="95%" />
      <Skeleton height={14} width="85%" />
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div style={{ padding: '1.5rem', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Skeleton height={20} width="40%" />
      <Skeleton height={14} width="80%" />
      <Skeleton height={14} width="60%" />
      <Skeleton height={36} width="30%" style={{ marginTop: 8 }} />
    </div>
  );
}
