import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Calendar, Clock, Copy, Check } from 'lucide-react';
import { blogPosts } from '../data/blogPosts';
import './Pages.css';

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const CodeBlock = ({ code, language }: { code: string; language: string }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ margin: '1.5rem 0', position: 'relative' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '0.5rem 1rem', background: 'var(--bg-color)',
        borderBottom: '1px solid var(--border-color)',
        fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
        color: 'var(--text-secondary)', textTransform: 'uppercase',
      }}>
        <span>{language}</span>
        <button
          onClick={handleCopy}
          style={{
            display: 'flex', alignItems: 'center', gap: '4px',
            background: 'none', border: 'none', color: copied ? 'var(--accent)' : 'var(--text-secondary)',
            cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
          }}
        >
          {copied ? <><Check size={12} /> copied</> : <><Copy size={12} /> copy</>}
        </button>
      </div>
      <pre style={{
        margin: 0, padding: '1rem', overflow: 'auto',
        background: 'var(--bg-secondary)', border: '1px solid var(--border-color)',
        borderTop: 'none', fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
        lineHeight: 1.6, color: 'var(--text-primary)',
      }}>
        <code>{code}</code>
      </pre>
    </div>
  );
};

const BlogPost = () => {
  const { id } = useParams<{ id: string }>();
  const post = blogPosts.find(p => p.id === id);

  if (!post) {
    return (
      <div className="page">
        <section className="section">
          <div className="container" style={{ textAlign: 'center', padding: '4rem 0' }}>
            <h1>Post Not Found</h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '1rem' }}>The blog post you are looking for does not exist.</p>
            <Link to="/blog" className="btn btn-primary" style={{ marginTop: '2rem', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <ArrowLeft size={18} /> Back to Blog
            </Link>
          </div>
        </section>
      </div>
    );
  }

  const renderContent = (content: string) => {
    const parts = content.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, idx) => {
      if (part.startsWith('```')) {
        const lines = part.slice(3, -3).split('\n');
        const language = lines[0].trim();
        const code = lines.slice(1).join('\n').trim();
        return <CodeBlock key={idx} code={code} language={language || 'code'} />;
      }

      const paragraphs = part.split('\n\n').filter(p => p.trim());
      
      return paragraphs.map((paragraph, pIdx) => {
        if (paragraph.startsWith('|')) {
          const rows = paragraph.split('\n').filter(r => r.trim());
          const headers = rows[0].split('|').filter(c => c.trim());
          const dataRows = rows.slice(2);
          return (
            <div key={`${idx}-${pIdx}`} style={{ overflowX: 'auto', margin: '1.5rem 0' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr>
                    {headers.map((h, i) => (
                      <th key={i} style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '2px solid var(--border)', color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {h.trim()}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dataRows.map((row, ri) => {
                    const cells = row.split('|').filter(c => c.trim());
                    return (
                      <tr key={ri}>
                        {cells.map((cell, ci) => (
                          <td key={ci} style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)', fontFamily: 'var(--font-mono)' }}>
                            {cell.trim()}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        }

        if (paragraph.startsWith('**') && paragraph.endsWith('**')) {
          return <h2 key={`${idx}-${pIdx}`} style={{ fontSize: '1.3rem', marginTop: '2rem', marginBottom: '1rem', fontFamily: 'var(--font-sans)' }}>{paragraph.replace(/\*\*/g, '')}</h2>;
        }

        if (paragraph.startsWith('**')) {
          const lines = paragraph.split('\n');
          return (
            <div key={`${idx}-${pIdx}`} style={{ marginBottom: '1.5rem' }}>
              {lines.map((line, lIdx) => {
                if (line.startsWith('**')) {
                  return <h3 key={lIdx} style={{ fontSize: '1.1rem', marginTop: '1.5rem', marginBottom: '0.5rem', fontFamily: 'var(--font-sans)' }}>{line.replace(/\*\*/g, '')}</h3>;
                }
                if (line.startsWith('- ')) {
                  return (
                    <div key={lIdx} style={{ display: 'flex', gap: '0.5rem', marginLeft: '1rem', marginBottom: '0.35rem', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--accent)' }}>›</span>
                      <span>{line.slice(2)}</span>
                    </div>
                  );
                }
                if (line.match(/^\d+\./)) {
                  return (
                    <div key={lIdx} style={{ display: 'flex', gap: '0.5rem', marginLeft: '1rem', marginBottom: '0.35rem', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--accent)', minWidth: '20px' }}>{line.match(/^\d+/)?.[0]}.</span>
                      <span>{line.replace(/^\d+\.\s*/, '')}</span>
                    </div>
                  );
                }
                return <p key={lIdx} style={{ marginBottom: '0.75rem', fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>{line}</p>;
              })}
            </div>
          );
        }

        return <p key={`${idx}-${pIdx}`} style={{ marginBottom: '1.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.9rem', lineHeight: 1.8 }}>{paragraph}</p>;
      });
    });
  };

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: '800px' }}>
          <motion.div {...fadeUp}>
            <Link to="/blog" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', marginBottom: '2rem' }}>
              <ArrowLeft size={14} /> back to blog
            </Link>

            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Calendar size={12} /> {new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={12} /> {post.readTime}
              </span>
            </div>

            <h1 style={{ fontSize: '2rem', lineHeight: 1.2, marginBottom: '1.5rem', fontFamily: 'var(--font-sans)' }}>
              <span className="text-gradient">{post.title}</span>
            </h1>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '2rem' }}>
              {post.tags.map(tag => (
                <span key={tag} className="meta-tag" style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)' }}>{tag}</span>
              ))}
            </div>
          </motion.div>

          <div className="blog-content">
            {renderContent(post.content)}
          </div>

          <div style={{ marginTop: '3rem', paddingTop: '2rem', borderTop: '1px solid var(--border)' }}>
            <Link to="/blog" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
              <ArrowLeft size={14} /> more articles
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default BlogPost;
