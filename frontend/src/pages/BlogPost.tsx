import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Calendar, Clock } from 'lucide-react';
import { blogData } from './Blog';
import './Pages.css';

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: easeFn },
};

const BlogPost = () => {
  const { id } = useParams<{ id: string }>();
  const post = blogData.find(p => p.id === id);

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

  const paragraphs = post.content.split('\n\n').filter(p => p.trim());

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: '800px' }}>
          <motion.div {...fadeUp}>
            <Link to="/blog" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', textDecoration: 'none', fontSize: '0.9rem', marginBottom: '2rem' }}>
              <ArrowLeft size={16} /> Back to Blog
            </Link>

            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Calendar size={14} /> {new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={14} /> {post.readTime}
              </span>
            </div>

            <h1 style={{ fontSize: '2.5rem', lineHeight: 1.2, marginBottom: '1.5rem' }}>
              <span className="text-gradient">{post.title}</span>
            </h1>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '2rem' }}>
              {post.tags.map(tag => (
                <span key={tag} className="meta-tag">{tag}</span>
              ))}
            </div>
          </motion.div>

          <div className="blog-content" style={{ lineHeight: 1.8, color: 'var(--text-primary)' }}>
            {paragraphs.map((paragraph, idx) => {
              if (paragraph.startsWith('|')) {
                const rows = paragraph.split('\n').filter(r => r.trim());
                const headers = rows[0].split('|').filter(c => c.trim());
                const dataRows = rows.slice(2);
                return (
                  <div key={idx} style={{ overflowX: 'auto', margin: '1.5rem 0' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                      <thead>
                        <tr>
                          {headers.map((h, i) => (
                            <th key={i} style={{ padding: '0.75rem', textAlign: 'left', borderBottom: '2px solid var(--border)', color: 'var(--accent)', fontWeight: 600 }}>
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
                                <td key={ci} style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)' }}>
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
                return <h2 key={idx} style={{ fontSize: '1.5rem', marginTop: '2rem', marginBottom: '1rem' }}>{paragraph.replace(/\*\*/g, '')}</h2>;
              }

              if (paragraph.startsWith('**')) {
                const parts = paragraph.split('\n');
                return (
                  <div key={idx} style={{ marginBottom: '1.5rem' }}>
                    {parts.map((part, pi) => {
                      if (part.startsWith('**')) {
                        return <h3 key={pi} style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>{part.replace(/\*\*/g, '')}</h3>;
                      }
                      if (part.startsWith('- ')) {
                        return <li key={pi} style={{ marginLeft: '1.5rem', marginBottom: '0.25rem' }}>{part.slice(2)}</li>;
                      }
                      if (part.match(/^\d+\./)) {
                        return <li key={pi} style={{ marginLeft: '1.5rem', marginBottom: '0.25rem', listStyleType: 'decimal' }}>{part.replace(/^\d+\.\s*/, '')}</li>;
                      }
                      return <p key={pi} style={{ marginBottom: '0.75rem' }}>{part}</p>;
                    })}
                  </div>
                );
              }

              return <p key={idx} style={{ marginBottom: '1.5rem' }}>{paragraph}</p>;
            })}
          </div>

          <div style={{ marginTop: '3rem', paddingTop: '2rem', borderTop: '1px solid var(--border)' }}>
            <Link to="/blog" className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <ArrowLeft size={18} /> More Articles
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default BlogPost;
