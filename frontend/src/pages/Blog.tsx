import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Calendar, Clock, ArrowRight, Leaf, Cpu, BarChart3, Globe } from 'lucide-react';
import './Pages.css';

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: easeFn },
};

interface BlogPost {
  id: string;
  title: string;
  excerpt: string;
  date: string;
  readTime: string;
  icon: React.ReactNode;
  tags: string[];
  content: string;
}

const blogPosts: BlogPost[] = [
  {
    id: 'carbon-aware-ai-routing',
    title: 'What Is Carbon-Aware AI Routing?',
    excerpt: 'How intelligent routing can reduce AI inference emissions by up to 70% without sacrificing quality.',
    date: '2025-01-15',
    readTime: '5 min read',
    icon: <Leaf size={24} />,
    tags: ['Green AI', 'Routing', 'Carbon Tracking'],
    content: `
AI inference is projected to consume more energy than training by 2027. Yet most optimization tools focus only on the training phase. Carbon-aware AI routing solves this by dynamically directing queries to data centers powered by renewable energy.

**How It Works:**

1. **Query Classification** — A lightweight classifier determines query complexity
2. **Carbon Intensity Check** — Real-time data from Electricity Maps API
3. **Smart Routing** — Queries are sent to the greenest available data center
4. **Verification** — Independent audit logs prove the carbon savings

**The Impact:**

A single GPT-4 query produces approximately 0.8g of CO₂. By routing to green regions (like Sweden or Norway), this drops to 0.05g — a 93% reduction.

**Code Example:**

\`\`\`python
# EcoQuery automatically routes to the greenest provider
import ecoquery

client = ecoquery.Client(api_key="eq_...")

response = client.chat(
    message="Explain quantum computing",
    # Automatically routes to lowest carbon intensity region
)

print(response.metadata.region)       # "se-stockholm"
print(response.metadata.co2_saved_g)  # 0.75g saved
print(response.metadata.carbon_score) # 9.2/10
\`\`\`

**Why It Matters:**

Companies are under increasing pressure to report and reduce their AI carbon footprint. Carbon-aware routing provides a measurable, verifiable way to do this without changing your AI models or infrastructure.
    `
  },
  {
    id: 'ai-carbon-footprint-crisis',
    title: 'The AI Carbon Footprint Crisis Nobody Is Talking About',
    excerpt: 'While everyone focuses on training emissions, inference is silently consuming more energy than ever.',
    date: '2025-01-10',
    readTime: '7 min read',
    icon: <Cpu size={24} />,
    tags: ['AI Emissions', 'Energy', 'Sustainability'],
    content: `
The AI industry has a dirty secret: while training gets all the attention, inference — the act of running queries — is the real energy consumer.

**The Numbers:**

- Training GPT-4 consumed ~50 GWh of electricity
- Daily inference for ChatGPT users: ~50 GWh
- By 2027, inference will consume 10x more energy than training

**Why This Happens:**

Every time someone asks ChatGPT a question, the model runs across thousands of GPUs. Multiply this by millions of daily users, and the energy consumption becomes staggering.

**Code: Tracking Your Inference Emissions**

\`\`\`python
# Calculate your AI carbon footprint
def calculate_co2(query_count, tokens_per_query, grid_intensity):
    """
    query_count: Number of queries per day
    tokens_per_query: Average tokens per query
    grid_intensity: g/kWh (e.g., 700 for India, 13 for Sweden)
    """
    energy_per_1k_tokens = 0.0002  # kWh
    total_tokens = query_count * tokens_per_query
    energy_kwh = (total_tokens / 1000) * energy_per_1k_tokens
    co2_grams = energy_kwh * grid_intensity
    return co2_grams

# India (coal-heavy grid)
india_co2 = calculate_co2(1000, 500, 700)
print(f"India: {india_co2:.2f}g CO₂/day")  # 70.00g

# Sweden (hydro/nuclear)
sweden_co2 = calculate_co2(1000, 500, 13)
print(f"Sweden: {sweden_co2:.4f}g CO₂/day")  # 1.30g

print(f"Reduction: {((india_co2 - sweden_co2) / india_co2 * 100):.0f}%")
\`\`\`

**The Solution:**

Carbon-aware routing doesn't eliminate inference energy use — it makes it cleaner. By sending queries to data centers powered by hydro, wind, or nuclear energy, we can reduce the carbon footprint of every AI interaction.
    `
  },
  {
    id: 'green-data-centers',
    title: 'Which Data Centers Are Actually Green?',
    excerpt: 'Not all data centers are created equal. Here is how to tell the difference.',
    date: '2025-01-05',
    readTime: '6 min read',
    icon: <Globe size={24} />,
    tags: ['Data Centers', 'Renewable Energy', 'Green Computing'],
    content: `
"Green data center" is a term thrown around loosely. Here is what actually makes a data center green.

**Carbon Intensity by Region:**

| Region | Carbon Intensity | Energy Source |
|--------|-----------------|---------------|
| Sweden | 13 g/kWh | Hydro/Nuclear |
| Norway | 13 g/kWh | Hydro |
| France | 55 g/kWh | Nuclear |
| Iceland | 0 g/kWh | Geothermal |
| US (Oregon) | 80 g/kWh | Hydro |
| India | 700 g/kWh | Coal |

**Code: Query Real-Time Carbon Intensity**

\`\`\`bash
# Check carbon intensity for any region
$ curl https://api.electricitymap.org/v3/carbon-intensity/se-stockholm

{
  "carbonIntensity": 13,
  "unit": "gCO2eq/kWh",
  "energySource": "hydro,nuclear",
  "timestamp": "2025-01-05T10:30:00Z"
}
\`\`\`

**What to Look For:**

1. **Renewable Energy Percentage** — Look for 100% renewable
2. **Carbon Intensity** — Below 100 g/kWh is considered green
3. **Power Usage Effectiveness (PUE)** — Lower is better (1.0 is perfect)
4. **Cooling Methods** — Free cooling (air/water) vs mechanical cooling

**How EcoQuery Uses This:**

EcoQuery automatically routes your AI queries to data centers with the lowest carbon intensity, using real-time data from the Electricity Maps API. No need to research individual providers.
    `
  },
  {
    id: 'measuring-ai-carbon',
    title: 'How to Measure Your AI Carbon Footprint',
    excerpt: 'A practical guide to tracking and reporting AI inference emissions.',
    date: '2024-12-28',
    readTime: '8 min read',
    icon: <BarChart3 size={24} />,
    tags: ['Carbon Accounting', 'ESG', 'Measurement'],
    content: `
Measuring AI carbon footprint is complex, but here is a simplified framework.

**The Formula:**

CO₂ = Energy Used × Carbon Intensity of Grid

**For AI Inference:**

CO₂ per query = (Tokens × Energy per 1K tokens) × Grid Carbon Intensity

**Example Calculation:**

- Query: 1000 tokens
- Energy per 1K tokens: 0.0002 kWh
- Grid intensity (India): 700 g/kWh
- CO₂: 0.14g per query

Now compare with green routing:

- Grid intensity (Sweden): 13 g/kWh
- CO₂: 0.0026g per query
- **Reduction: 98%**

**Code: Full Measurement Script**

\`\`\`python
import json
from datetime import datetime

class CarbonTracker:
    def __init__(self, api_key):
        self.api_key = api_key
        self.log = []
    
    def track_query(self, model, tokens, region, co2):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "tokens": tokens,
            "region": region,
            "co2_grams": co2
        }
        self.log.append(entry)
        return entry
    
    def total_co2(self):
        return sum(e["co2_grams"] for e in self.log)
    
    def savings_vs_baseline(self, baseline_intensity=700):
        baseline = sum(
            e["tokens"] / 1000 * 0.0002 * baseline_intensity 
            for e in self.log
        )
        return baseline - self.total_co2()
    
    def export_report(self):
        return {
            "total_queries": len(self.log),
            "total_co2_g": self.total_co2(),
            "savings_g": self.savings_vs_baseline(),
            "log": self.log
        }

# Usage
tracker = CarbonTracker("eq_...")
tracker.track_query("deepseek-v4-flash", 500, "se-stockholm", 0.001)
tracker.track_query("mimo-v2.5", 800, "no-oslo", 0.002)
print(json.dumps(tracker.export_report(), indent=2))
\`\`\`

**What to Track:**

1. Total queries per day/month
2. Average tokens per query
3. Providers used and their regions
4. Carbon intensity of each region
5. Total CO₂ saved vs baseline

**Reporting for ESG:**

Many companies now need to report AI emissions in their ESG reports. EcoQuery provides audit logs and certificates that can be used directly in sustainability reporting.
    `
  },
  {
    id: 'future-of-green-ai',
    title: 'The Future of Green AI: What Comes Next',
    excerpt: 'From carbon credits to neuromorphic computing — the next decade of sustainable AI.',
    date: '2024-12-20',
    readTime: '6 min read',
    icon: <Leaf size={24} />,
    tags: ['Future Tech', 'Innovation', 'Sustainability'],
    content: `
The green AI movement is just beginning. Here is what the next decade looks like.

**Short Term (2025-2027):**

- Carbon-aware routing becomes standard
- AI providers start reporting inference emissions
- ESG frameworks include AI carbon footprint
- Carbon credits for green AI inference

**Medium Term (2027-2030):**

- Edge computing reduces data center dependence
- More efficient model architectures (sparsity, quantization)
- Renewable energy becomes default for tech companies
- Carbon pricing affects AI deployment decisions

**Long Term (2030+):**

- Neuromorphic computing (brain-inspired chips) — 1000x more efficient
- Quantum computing for optimization problems
- AI self-optimizing for energy efficiency
- Zero-carbon inference possible

**Code: The Green AI Roadmap**

\`\`\`yaml
# green-ai-roadmap.yaml
version: "1.0"
milestones:
  2025:
    - Carbon-aware routing adoption
    - Real-time emission tracking
    - ESG reporting integration
  
  2027:
    - Edge inference (on-device)
    - Sparse model architectures
    - 100% renewable data centers
  
  2030:
    - Neuromorphic chips
    - Carbon-negative AI
    - Self-optimizing inference

metrics:
  carbon_per_query_target: "0.001g"
  renewable_energy_target: "100%"
  pue_target: 1.1
\`\`\`

**What You Can Do Now:**

1. Start tracking your AI carbon footprint today
2. Use carbon-aware routing where possible
3. Choose providers committed to renewable energy
4. Include AI emissions in your sustainability reports

The best time to start is now. The second best time is tomorrow. But the carbon you save today matters more than the carbon you save tomorrow.
    `
  }
];

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
                  <div style={{ color: 'var(--accent)', display: 'flex' }}>{post.icon}</div>
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

export const blogData = blogPosts;
export default Blog;
