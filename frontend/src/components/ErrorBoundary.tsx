import React from 'react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  componentDidCatch(error: Error) {
    console.error('ErrorBoundary caught:', error);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: '60vh', padding: '2rem', textAlign: 'center', color: '#e0e0e0'
        }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#aaa', margin: '1rem 0' }}>
            An unexpected error occurred. Please try again.
          </p>
          <button onClick={this.handleReset} style={{
            padding: '0.75rem 2rem', background: '#4fc3f7', color: '#0a0a0a',
            border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600
          }}>
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
