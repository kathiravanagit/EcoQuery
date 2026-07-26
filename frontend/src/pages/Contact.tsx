import React, { useCallback, useState, useEffect, FormEvent } from 'react';
import { motion } from 'framer-motion';
import { useForm, ValidationError } from '@formspree/react';
import { Send, Mail, MapPin, Clock } from 'lucide-react';
import './Pages.css';

const Contact = () => {
  const [state, formspreeSubmit] = useForm("meeylabz");
  const formRef = React.useRef<HTMLFormElement>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  useEffect(() => {
    if (state.succeeded) {
      setShowSuccess(true);
      const timer = setTimeout(() => setShowSuccess(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [state.succeeded]);

  const handleSubmit = useCallback((e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    formRef.current?.reset();
    formspreeSubmit(e);
  }, [formspreeSubmit]);

  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>Get in <span className="text-gradient">Touch</span></h1>
            <p className="page-subtitle">Have questions? We'd love to hear from you.</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="contact-grid">
            <motion.div className="contact-info" initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <div className="contact-item"><Mail size={20} className="text-accent" /><div><h4>Email</h4><p>kathiravanawork@gmail.com</p></div></div>
              <div className="contact-item"><MapPin size={20} className="text-accent" /><div><h4>Location</h4><p>Puducherry, India</p></div></div>
              <div className="contact-item"><Clock size={20} className="text-accent" /><div><h4>Response Time</h4><p>Within 24 hours</p></div></div>
            </motion.div>

            <motion.form ref={formRef} className="contact-form card" onSubmit={handleSubmit} initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <label htmlFor="contact-name" style={{ display: 'none' }}>Your Name</label>
              <input id="contact-name" type="text" name="name" placeholder="Your Name" required />
              <label htmlFor="contact-email" style={{ display: 'none' }}>Your Email</label>
              <input id="contact-email" type="email" name="email" placeholder="Your Email" required />
              <ValidationError prefix="Email" field="email" errors={state.errors} />
              <label htmlFor="contact-message" style={{ display: 'none' }}>Your Message</label>
              <textarea id="contact-message" name="message" rows={5} placeholder="Your Message" required></textarea>
              <ValidationError prefix="Message" field="message" errors={state.errors} />
              <button type="submit" className="btn btn-primary" disabled={state.submitting}>
                {showSuccess ? 'Message Sent!' : state.submitting ? 'Sending...' : 'Send Message'}
                <Send size={16} />
              </button>
            </motion.form>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Contact;
