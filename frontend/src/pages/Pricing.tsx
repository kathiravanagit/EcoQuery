import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Check, ArrowRight } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import './Pages.css';

const plans = [
  {
    name: 'Starter',
    price: 'Free',
    desc: 'For individual developers exploring carbon-aware routing.',
    features: ['100 queries/day', 'Basic routing', 'Mock carbon data', 'Community support'],
    cta: 'Get Started',
    featured: false,
  },
  {
    name: 'Pro',
    price: '$49',
    period: '/month',
    desc: 'For teams who need real carbon data and higher throughput.',
    features: ['10,000 queries/day', 'Electricity Maps integration', 'Real carbon routing', 'Audit log access', 'Email support', 'API key access'],
    cta: 'Subscribe',
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    desc: 'For organizations requiring dedicated infrastructure and SLAs.',
    features: ['Unlimited queries', 'Custom model routing', 'Private ledger', 'SSO & RBAC', 'Dedicated support', 'SLA guarantee'],
    cta: 'Contact Sales',
    featured: false,
  },
];

const Pricing = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleClick = (plan: typeof plans[0]) => {
    if (plan.name === 'Starter') {
      navigate('/dashboard');
    } else {
      toast('info', `"${plan.name}" plan is still under development. Thank you for your interest!`);
    }
  };

  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>Simple <span className="text-gradient">Pricing</span></h1>
            <p className="page-subtitle">Start free, scale as you grow. No hidden fees.</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="pricing-grid">
            {plans.map((plan, i) => (
              <motion.div
                key={i}
                className={`pricing-card card ${plan.featured ? 'pricing-featured' : ''}`}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                {plan.featured && <div className="pricing-badge">Most Popular</div>}
                <h3 className="pricing-name">{plan.name}</h3>
                <div className="pricing-price">
                  <span className="price-amount">{plan.price}</span>
                  {plan.period && <span className="price-period">{plan.period}</span>}
                </div>
                <p className="pricing-desc">{plan.desc}</p>
                <ul className="pricing-features">
                  {plan.features.map((f, j) => (
                    <li key={j}><Check size={16} className="text-accent" /> {f}</li>
                  ))}
                </ul>
                <button onClick={() => handleClick(plan)} className={`btn ${plan.featured ? 'btn-primary' : 'btn-secondary'}`} style={{ width: '100%' }}>
                  {plan.cta} <ArrowRight size={16} />
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default Pricing;
