import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Calendar, Clock, ArrowRight, Leaf, Cpu, BarChart3, Globe } from 'lucide-react';
import { blogPosts } from '../data/blogPosts';
import './Pages.css';

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const iconMap: Record<string, React.ReactNode> = {
  leaf: <Leaf size={24} />,
  cpu: <Cpu size={24} />,
  globe: <Globe size={24} />,
  barChart: <BarChart3 size={24} />,
};

const Blog = () => {
  return (
    <div className="page">
      <section className="section">
        <div className="container">
          <motion.div className="section-header" {...fadeUp}>
            <h1>Blog — <span className="text-gradient">Green AI Insights</span></h1>
            <p>Research, guides, and insights on sustainable AI and carbon-aware computing.</p>
          </motion.div>

          <div className="blog-grid" style={{ display: 'grid', gap: '2rem', marginTop: '3rem' }}>
            {blogPosts.map((post, idx) => (
              <motion.article
                key={post.id}
                className="card blog-card"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                style={{ padding: '2rem' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ color: 'var(--accent)', display: 'flex' }}>{iconMap[post.iconKey]}</div>
                  <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Calendar size={14} /> {new Date(post.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={14} /> {post.readTime}
                    </span>
                  </div>
                </div>

                <h2 style={{ fontSize: '1.5rem', marginBottom: '0.75rem', lineHeight: 1.3 }}>
                  <Link to={`/blog/${post.id}`} className="text-gradient" style={{ textDecoration: 'none' }}>
                    {post.title}
                  </Link>
                </h2>

                <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: '1rem' }}>
                  {post.excerpt}
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
                  {post.tags.map(tag => (
                    <span key={tag} className="meta-tag" style={{ fontSize: '0.75rem' }}>{tag}</span>
                  ))}
                </div>

                <Link to={`/blog/${post.id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)', fontSize: '0.9rem', textDecoration: 'none', fontWeight: 500 }}>
                  Read More <ArrowRight size={16} />
                </Link>
              </motion.article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default Blog;
