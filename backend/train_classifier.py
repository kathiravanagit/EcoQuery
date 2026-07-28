"""
Train a TF-IDF + LogisticRegression classifier for EcoQuery query tiering.
Generates 1,000 synthetic prompts per tier (simple / medium / complex)
for a total of 3,000 labeled examples.

Usage:
    python backend/train_classifier.py

Output:
    backend/models/vectorizer.pkl   — fitted CountVectorizer / TfidfVectorizer
    backend/models/classifier.pkl   — trained sklearn pipeline
    backend/models/training_data.csv — the generated dataset (for inspection / replacement)
"""

import os
import random
import csv
import logging
import joblib

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_classifier")

random.seed(42)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Synthetic prompt templates ──────────────────────────────────────────

SIMPLE_TEMPLATES = [
    "What is the capital of {country}?",
    "How do I {verb} a {noun}?",
    "What time is it in {city}?",
    "Define {term}",
    "What is {concept}?",
    "Is {statement} true?",
    "Hello",
    "Hi there",
    "Good morning",
    "Thanks",
    "What's the weather in {city}?",
    "Who wrote {book}?",
    "What year was {event}?",
    "How tall is {thing}?",
    "Tell me a joke",
    "What does {acronym} stand for?",
    "What is your name?",
    "How are you?",
    "What is 2 + 2?",
    "Translate '{word}' to French",
    "What is the population of {city}?",
    "When was {person} born?",
    "What color is the sky?",
    "Where is {place} located?",
    "What is the opposite of {word}?",
    "How old is {person}?",
    "What day is it today?",
    "Count to 10",
    "Say hello in Spanish",
    "What is the square root of {number}?",
]

MEDIUM_TEMPLATES = [
    "Explain the difference between {concept_a} and {concept_b}",
    "How does {technology} work under the hood?",
    "Compare and contrast {topic_a} with {topic_b}",
    "Why does {phenomenon} happen?",
    "What are the pros and cons of {topic}?",
    "How do you implement a {algorithm} in Python?",
    "Describe the architecture of {system}",
    "What factors influence {outcome}?",
    "How would you approach designing a {system}?",
    "Explain the concept of {concept} to a beginner",
    "What causes {phenomenon} and how can it be mitigated?",
    "Walk me through the steps to {task}",
    "How does {concept} relate to {other_concept}?",
    "What are the tradeoffs between {option_a} and {option_b}?",
    "Can you summarize {topic} in simple terms?",
    "How do I set up a {technology} environment for development?",
    "What is the best way to {task} efficiently?",
    "Explain the key differences between {framework_a} and {framework_b}",
    "How would you debug a {problem} in production?",
    "What are the best practices for {activity}?",
    "Describe how {protocol} works step by step",
    "Why do we use {technology} instead of {alternative}?",
    "What is the time complexity of {algorithm} and why?",
    "How does caching improve {system} performance?",
    "Compare {programming_language} with {other_language} for {use_case}",
    "What are the ethical implications of {technology}?",
    "How do databases handle {scenario} efficiently?",
    "Explain the concept of {cs_concept} with a real example",
    "What is the role of {component} in a {system}?",
    "How would you optimize a {process} that is running slowly?",
]

COMPLEX_TEMPLATES = [
    "Write a complete Python implementation of {algorithm} with O(n log n) complexity including edge case handling and unit tests",
    "Design a full architecture for a {system_type} that handles {requirement} while maintaining {constraint}",
    "Analyze the carbon footprint implications of deploying {model_type} across {region_count} data center regions, considering {factor_a} and {factor_b}",
    "Derive the mathematical formula for {mathematical_concept} and implement it efficiently",
    "Build a complete {framework} application with authentication, rate limiting, and database integration",
    "Write a detailed technical specification for a {system_type} that must support {scale} concurrent users with {uptime} availability",
    "Implement a machine learning pipeline that preprocesses {data_type}, trains a {model_type}, and deploys it via {platform}",
    "Design a fault-tolerant distributed system for {use_case} with replication, sharding, and disaster recovery",
    "Prove that {algorithm} has a worst-case complexity of O({complexity}) using mathematical induction or recurrence relations",
    "Create a comprehensive migration strategy from {old_tech} to {new_tech} covering schema changes, data integrity, rollback planning, and zero-downtime deployment",
    "Analyze the following code for security vulnerabilities: ``` {code_snippet} ```",
    "Design a RESTful API for a {domain} platform with proper HATEOAS constraints, pagination, filtering, and rate limiting",
    "Write a compiler for a minimal {language_type} language including lexer, parser, AST, and code generation",
    "Implement a distributed consensus algorithm like Raft or Paxos from scratch",
    "Design a data warehouse schema for {domain} with slowly changing dimensions, fact tables, and star schema optimization",
    "Develop a real-time monitoring system that aggregates metrics from {source_count} sources and triggers alerts based on anomaly detection",
    "Create a detailed cost-benefit analysis comparing {option_a} vs {option_b} for a {scale} deployment including operational overhead, licensing, and team training",
    "Write a custom React hook for {use_case} that handles loading states, error boundaries, cache invalidation, and optimistic updates",
    "Design a CI/CD pipeline for a microservices architecture with canary deployments, rollback automation, and integration testing",
    "Implement a concurrent data structure that is thread-safe and lock-free for {use_case}",
    "Write a detailed comparative analysis of {framework_a}, {framework_b}, and {framework_c} for {use_case} considering performance, ecosystem, learning curve, and community support",
    "Design a full authentication system including OAuth 2.0, JWT, refresh tokens, MFA, and session management",
    "Implement a query optimizer that rewrites {query_type} for better performance using cost-based optimization techniques",
    "Create a comprehensive test suite for a {system_type} including unit, integration, end-to-end, and performance tests",
    "Design a caching strategy for a {data_pattern} workload that balances memory usage, hit rate, and stale data tolerance",
    "Write an interpreter for {language_type} with proper scoping, closures, and garbage collection",
    "Design a recommendation system using collaborative filtering and content-based approaches with hybrid scoring",
    "Implement a rate limiter that supports token bucket, leaky bucket, and sliding window algorithms",
    "Create a disaster recovery plan for a cloud-native application including RPO, RTO, backup strategies, and failover testing",
    "Design and implement a full-text search engine with inverted indexes, relevance scoring, and typo tolerance",
]

# ── Fill-in pools ───────────────────────────────────────────────────────

_countries = ["France", "Japan", "Brazil", "India", "Germany", "Australia", "Egypt", "Canada"]
_cities = ["Tokyo", "Paris", "London", "Berlin", "Mumbai", "São Paulo", "Sydney", "Cairo"]
_terms = ["API", "recursion", "encryption", "blockchain", "quantum computing", "relational database", "microservices", "containerization"]
_concepts = ["machine learning", "cloud computing", "functional programming", "OAuth 2.0", "REST", "graph theory", "Big O notation", "distributed systems"]
_verbs = ["install", "configure", "deploy", "compile", "debug", "test", "optimize", "refactor"]
_nouns = ["server", "database", "API", "application", "container", "function", "class", "pipeline"]
_people = ["Albert Einstein", "Ada Lovelace", "Alan Turing", "Grace Hopper", "Linus Torvalds", "Guido van Rossum"]
_events = ["World War II", "the Moon landing", "the invention of the internet", "the Renaissance", "the Industrial Revolution"]
_books = ["1984", "The Great Gatsby", "Pride and Prejudice", "To Kill a Mockingbird", "The Lord of the Rings"]
_things = ["Mount Everest", "the Eiffel Tower", "the Great Wall of China", "the Empire State Building", "the Burj Khalifa"]
_places = ["the Amazon rainforest", "the Sahara Desert", "Antarctica", "the Great Barrier Reef", "the Himalayas"]
_words = ["hot", "big", "fast", "bright", "strong", "happy", "dark", "deep"]
_numbers = list(range(2, 100))
_acronyms = ["API", "SQL", "HTTP", "HTML", "CSS", "JSON", "YAML", "REST"]

_topics = [
    "cloud computing", "machine learning", "microservices", "containerization",
    "serverless architecture", "edge computing", "CI/CD", "DevOps",
]
_concept_a = ["monolithic architecture", "SQL databases", "waterfall methodology"]
_concept_b = ["microservices", "NoSQL databases", "agile methodology"]
_technologies = ["Kubernetes", "Docker", "React", "Django", "PostgreSQL", "Redis", "Kafka", "TensorFlow"]
_algorithms = ["quicksort", "merge sort", "binary search", "Dijkstra's algorithm", "A* search", "dynamic programming", "Dijkstra", "merge sort"]
_phenomena = ["climate change", "inflation", "economic recessions", "the greenhouse effect", "data breaches"]
_systems = ["e-commerce platform", "real-time chat app", "streaming service", "social network", "SaaS product", "payment gateway"]
_outcomes = ["customer retention", "conversion rates", "system performance", "code quality", "team productivity"]
_tasks = ["set up a CI/CD pipeline", "deploy a web application", "optimize a database query", "migrate to the cloud", "secure an API"]
_options = ["microservices", "monolith", "serverless", "edge computing", "cloud-native"]
_frameworks = ["React", "Vue", "Angular", "Django", "Flask", "FastAPI", "Spring Boot", "Rails"]
_languages = ["Python", "JavaScript", "Go", "Rust", "TypeScript", "Java", "C++", "Scala", "Elixir"]
_alts = ["Node.js", "Ruby", "PHP", "C#", "Kotlin"]
_use_cases = ["web development", "data science", "real-time systems", "embedded systems", "enterprise applications"]
_components = ["load balancer", "message queue", "database", "cache layer", "API gateway", "reverse proxy"]
_params_scenario = ["high concurrency", "read-heavy workloads", "write-heavy workloads", "eventual consistency requirements"]
_cs_concepts = ["cache invalidation", "load balancing", "database indexing", "distributed consensus", "consistent hashing", "event sourcing"]
_protocols = ["TCP/IP", "HTTP/2", "gRPC", "GraphQL", "WebSocket", "MQTT"]
_activities = ["code review", "CI/CD", "testing", "deployment", "monitoring", "incident response"]

_algo_complex = ["quicksort", "merge sort", "binary search tree", "Dijkstra's algorithm", "A*", "dynamic programming", "Bloom filter", "consistent hashing"]
_model_types = ["GPT-4", "BERT", "ResNet-50", "Llama 3", "Stable Diffusion", "whisper"]
_factors = ["regional grid carbon intensity", "time-of-day pricing", "cooling efficiency", "hardware utilization"]
_data_types = ["text", "image", "time-series", "tabular", "graph"]
_platforms = ["AWS SageMaker", "Google Vertex AI", "Azure ML", "Hugging Face", "MLflow"]
_old_techs = ["Jenkins", "MySQL", "Apache", "SOAP", "Monolithic"]
_new_techs = ["GitHub Actions", "PostgreSQL", "Nginx", "REST", "Microservices"]
_domains = ["e-commerce", "healthcare", "fintech", "education", "logistics"]
_lang_types = ["scripting", "compiled", "functional", "logic", "esoteric"]
_data_patterns = ["read-heavy", "write-heavy", "mixed workload", "time-series", "event-driven"]
_snippets = [
    "SELECT * FROM users WHERE id = {input};",
    "eval(request.GET['code'])",
    "strcpy(buffer, user_input);",
    "<img src=x onerror=alert(1)>",
]


def _fill(template: str, pools: dict) -> str:
    """Replace {placeholders} with random values from their respective pools."""
    result = template
    for key, values in pools.items():
        placeholder = "{" + key + "}"
        if placeholder in result:
            result = result.replace(placeholder, str(random.choice(values)), 1)
    return result


def generate_prompts(templates, pools, count: int) -> list[str]:
    """Generate `count` prompts by sampling templates and filling placeholders."""
    prompts = []
    for _ in range(count):
        tpl = random.choice(templates)
        prompt = _fill(tpl, pools)
        prompts.append(prompt)
    return prompts


def main():
    logger.info("Generating 3,000 synthetic prompts (1,000 per tier)…")

    shared_pools = {
        "country": _countries, "city": _cities, "term": _terms, "concept": _concepts,
        "verb": _verbs, "noun": _nouns, "person": _people, "event": _events,
        "book": _books, "thing": _things, "place": _places, "word": _words,
        "number": _numbers, "acronym": _acronyms, "topic": _topics,
        "concept_a": _concept_a, "concept_b": _concept_b, "technology": _technologies,
        "algorithm": _algorithms, "phenomenon": _phenomena, "system": _systems,
        "outcome": _outcomes, "task": _tasks, "option_a": _options, "option_b": _options,
        "framework_a": _frameworks, "framework_b": _frameworks, "framework_c": _frameworks,
        "programming_language": _languages, "other_language": _alts, "use_case": _use_cases,
        "cs_concept": _cs_concepts, "protocol": _protocols, "activity": _activities,
        "alternative": _alts, "component": _components, "scenario": _params_scenario,
        "model_type": _model_types, "factor_a": _factors, "factor_b": _factors,
        "data_type": _data_types, "platform": _platforms, "old_tech": _old_techs,
        "new_tech": _new_techs, "domain": _domains, "language_type": _lang_types,
        "data_pattern": _data_patterns, "code_snippet": _snippets,
    }

    simple_pools = {**shared_pools, "statement": _concepts, "concept": _concepts}
    medium_pools = {**shared_pools, "other_concept": _concepts, "framework": _frameworks, "other_language": _alts}
    complex_pools = {**shared_pools, "algo_complex": _algo_complex,
                     "region_count": [5, 8, 13, 20],
                     "requirement": ["high availability", "horizontal scalability", "sub-100ms latency", "multi-tenancy"],
                     "constraint": ["99.99% uptime", "sub-second response", "ACID compliance", "GDPR compliance"],
                     "scale": ["100k", "1M", "10M", "100M"],
                     "uptime": ["99.9%", "99.99%", "99.999%"],
                     "source_count": [5, 10, 50, 100],
                     "query_type": ["SQL", "GraphQL", "SPARQL", "PromQL"]}

    simple_prompts = generate_prompts(SIMPLE_TEMPLATES, simple_pools, 1000)
    medium_prompts = generate_prompts(MEDIUM_TEMPLATES, medium_pools, 1000)
    complex_prompts = generate_prompts(COMPLEX_TEMPLATES, complex_pools, 1000)

    all_texts = simple_prompts + medium_prompts + complex_prompts
    all_labels = ["simple"] * 1000 + ["medium"] * 1000 + ["complex"] * 1000

    # Save CSV for inspection / manual refinement
    csv_path = os.path.join(MODEL_DIR, "training_data.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label"])
        for text, label in zip(all_texts, all_labels):
            writer.writerow([text, label])
    logger.info("Saved %d rows to %s", len(all_texts), csv_path)

    # Train / eval split
    X_train, X_test, y_train, y_test = train_test_split(
        all_texts, all_labels, test_size=0.2, random_state=42, stratify=all_labels
    )

    logger.info("Training TF-IDF + LogisticRegression pipeline…")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10000, sublinear_tf=True)),
        ("clf", LogisticRegression(multi_class="multinomial", solver="lbfgs", max_iter=1000, random_state=42)),
    ])

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logger.info("Test accuracy: %.2f%%", acc * 100)
    logger.info("\n" + classification_report(y_test, y_pred, target_names=["simple", "medium", "complex"]))

    # Export
    vectorizer_path = os.path.join(MODEL_DIR, "vectorizer.pkl")
    model_path = os.path.join(MODEL_DIR, "classifier.pkl")

    # Export the fitted TF-IDF separately so classifier.py can inspect it if needed
    joblib.dump(pipeline.named_steps["tfidf"], vectorizer_path)
    joblib.dump(pipeline.named_steps["clf"], model_path)

    # Also export the full pipeline for convenience
    pipeline_path = os.path.join(MODEL_DIR, "pipeline.pkl")
    joblib.dump(pipeline, pipeline_path)

    logger.info("Exported model files:")
    logger.info("  vectorizer  → %s", vectorizer_path)
    logger.info("  classifier  → %s", model_path)
    logger.info("  pipeline    → %s", pipeline_path)


if __name__ == "__main__":
    main()
