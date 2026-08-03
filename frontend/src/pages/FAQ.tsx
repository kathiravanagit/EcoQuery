import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, ChevronUp, HelpCircle } from 'lucide-react';
import './Pages.css';

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

interface FAQItem {
  question: string;
  answer: string;
}

const faqCategories = [
  {
    category: 'General',
    items: [
      {
        question: 'What is EcoQuery?',
        answer: 'EcoQuery is a carbon-aware AI query routing platform that automatically directs your AI queries to data centers powered by renewable energy. It reduces your AI carbon footprint by up to 93% without changing your AI models or infrastructure.'
      },
      {
        question: 'How does EcoQuery reduce AI carbon emissions?',
        answer: 'EcoQuery uses real-time carbon intensity data from the Electricity Maps API to route queries to the greenest available data centers. For example, data centers in Sweden (13 g/kWh) produce 98% less CO₂ than those in India (700 g/kWh).'
      },
      {
        question: 'Is EcoQuery free to use?',
        answer: 'Yes, EcoQuery offers a free tier that includes basic carbon-aware routing and tracking. Pro and Enterprise plans are available for teams needing advanced features like custom models, priority support, and detailed ESG reporting.'
      },
      {
        question: 'Who is EcoQuery for?',
        answer: 'EcoQuery is for developers, data scientists, and companies who want to reduce their AI carbon footprint. It is especially useful for organizations with ESG reporting requirements or sustainability commitments.'
      }
    ] as FAQItem[]
  },
  {
    category: 'How It Works',
    items: [
      {
        question: 'How does the carbon-aware routing work?',
        answer: 'When you send a query, EcoQuery: (1) Classifies the query complexity, (2) Checks real-time carbon intensity for available data centers, (3) Routes to the greenest provider, (4) Logs the carbon savings in an immutable audit trail.'
      },
      {
        question: 'Does routing to green data centers affect response quality?',
        answer: 'No. EcoQuery uses the same high-quality models (Llama, Mistral, DeepSeek) regardless of which data center processes them. The only difference is the location, which affects carbon footprint but not model quality.'
      },
      {
        question: 'What AI models does EcoQuery support?',
        answer: 'EcoQuery supports free-tier models including DeepSeek V4 Flash, Mistral 7B, Llama 3.1 8B, and others. Pro users can access premium models like GPT-4 and Claude with carbon-aware routing.'
      },
      {
        question: 'How accurate is the carbon tracking?',
        answer: 'EcoQuery uses real-time data from the Electricity Maps API combined with IEA baselines. All estimates are clearly marked as calculated values. The system includes an independent verification engine that audits carbon savings.'
      }
    ] as FAQItem[]
  },
  {
    category: 'Technical',
    items: [
      {
        question: 'How do I integrate EcoQuery into my application?',
        answer: 'EcoQuery provides a simple REST API. Replace your current AI provider endpoint with EcoQuery\'s /api/chat endpoint. We support OpenAI-compatible formats, so integration takes just a few lines of code.'
      },
      {
        question: 'Is there an SDK or library available?',
        answer: 'Currently, EcoQuery provides REST API endpoints that work with any HTTP client. We are working on official SDKs for Python, JavaScript, and Go. Check our GitHub repository for updates.'
      },
      {
        question: 'Can I use my own API keys with EcoQuery?',
        answer: 'Yes. EcoQuery supports bringing your own API keys for OpenRouter, Anthropic, and other providers. Your keys are encrypted and never shared with third parties.'
      },
      {
        question: 'What regions does EcoQuery support?',
        answer: 'EcoQuery routes queries to green data centers in Sweden, Norway, France, Iceland, Canada, and Oregon (US). We are continuously adding new regions with high renewable energy coverage.'
      },
      {
        question: 'How does the verification system work?',
        answer: 'EcoQuery\'s verification engine logs every query with: model used, region, carbon intensity, and an SHA-256 integrity hash. This creates an immutable audit trail for ESG reporting and compliance.'
      }
    ] as FAQItem[]
  },
  {
    category: 'Account & Billing',
    items: [
      {
        question: 'How do I create an account?',
        answer: 'Click "Sign Up" on the homepage. You can register with email or sign in with Google. Free accounts are created instantly with no credit card required.'
      },
      {
        question: 'Can I upgrade or downgrade my plan anytime?',
        answer: 'Yes. You can upgrade or downgrade your plan at any time from your Dashboard. Changes take effect immediately, and billing is adjusted pro-rata.'
      },
      {
        question: 'Do you offer discounts for startups or open source?',
        answer: 'Yes. We offer 50% off Pro plans for startups (under 2 years old) and free Pro plans for open source projects with public repos. Contact support@ecoquery.app for details.'
      },
      {
        question: 'How do I delete my account?',
        answer: 'Go to Settings > Account > Delete Account. You will need to confirm your password. All your data will be permanently deleted within 30 days.'
      }
    ] as FAQItem[]
  }
];

const FAQAccordion = ({ item }: { item: FAQItem }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="faq-item" style={{ borderBottom: '1px solid var(--border)' }}>
      <button
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '1.25rem 0', background: 'none', border: 'none', cursor: 'pointer',
          textAlign: 'left', color: 'var(--text-primary)', fontSize: '1rem', fontWeight: 500,
        }}
      >
        <span style={{ paddingRight: '1rem' }}>{item.question}</span>
        {isOpen ? <ChevronUp size={20} style={{ color: 'var(--accent)', flexShrink: 0 }} /> : <ChevronDown size={20} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />}
      </button>
      <motion.div
        initial={false}
        animate={{ height: isOpen ? 'auto' : 0, opacity: isOpen ? 1 : 0 }}
        transition={{ duration: 0.3 }}
        style={{ overflow: 'hidden' }}
      >
        <p style={{ paddingBottom: '1.25rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          {item.answer}
        </p>
      </motion.div>
    </div>
  );
};

const FAQ = () => {
  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: '800px' }}>
          <motion.div className="section-header" {...fadeUp}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
              <HelpCircle size={48} style={{ color: 'var(--accent)' }} />
            </div>
            <h1>Frequently Asked <span className="text-gradient">Questions</span></h1>
            <p>Everything you need to know about EcoQuery and carbon-aware AI routing.</p>
          </motion.div>

          <div style={{ marginTop: '3rem' }}>
            {faqCategories.map((category, idx) => (
              <motion.div
                key={category.category}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                style={{ marginBottom: '2.5rem' }}
              >
                <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem', color: 'var(--accent)' }}>
                  {category.category}
                </h2>
                <div className="card" style={{ padding: '0.5rem 1.5rem' }}>
                  {category.items.map((item, i) => (
                    <FAQAccordion key={i} item={item} />
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            className="card"
            style={{ padding: '2rem', textAlign: 'center', marginTop: '2rem' }}
            {...fadeUp}
          >
            <h3 style={{ marginBottom: '0.75rem' }}>Still have questions?</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Can not find the answer you are looking for? Contact our support team.
            </p>
            <a href="mailto:kathiravanawork@gmail.com" className="btn btn-primary">
              Contact Support
            </a>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default FAQ;
