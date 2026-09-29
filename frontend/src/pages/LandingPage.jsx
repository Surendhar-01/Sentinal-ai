import React, { useState } from 'react';
import { ShieldCheck, BrainCircuit, Workflow, FileText, LockKeyhole, Cpu, Server, CheckCircle2, ChevronRight, Lock, Network, Cog } from 'lucide-react';
import '../landing.css';

export default function LandingPage({ onEnterApp }) {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    {
      title: "Manufacturing/PSUs",
      content: "Upload a scanned P&ID (Piping & Instrument Diagram). The AI extracts key metrics and generates an inspection report in Word."
    },
    {
      title: "Defense/Gov",
      content: "Analyze unreleased schematics and cross-reference them against local SOPs without data ever leaving the secure facility."
    },
    {
      title: "Corporate Finance",
      content: "Securely process vendor negotiations and confidential board presentations locally."
    }
  ];

  return (
    <div className="landing-wrapper">
      {/* Navbar */}
      <div className="lp-navbar glass">
        <div className="lp-nav-brand">
          <ShieldCheck size={28} />
          OmniVault AI
        </div>
        <div className="lp-nav-links">
          <a href="#features">Features</a>
          <a href="#use-cases">Use Cases</a>
          <a href="#specs">Technical Specs</a>
        </div>
        <div className="lp-nav-actions">
          <button className="lp-btn" onClick={onEnterApp}>
            Log In
          </button>
          <button className="lp-btn primary" onClick={onEnterApp}>
            Request a Local Demo <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Hero Section */}
      <div className="lp-hero">
        <h1>Cloud-Tier AI. <br/><span>Zero Cloud Risk.</span></h1>
        <p>The first fully air-gapped, agentic AI workbench built for defense, energy, and critical industries. Automate your most sensitive knowledge work entirely on your own hardware.</p>
        <div className="lp-hero-ctas">
          <button className="lp-btn primary" onClick={onEnterApp}>
            Request a Local Demo <ChevronRight size={18} />
          </button>
          <button className="lp-btn" onClick={() => document.getElementById('specs').scrollIntoView({behavior: 'smooth'})}>
            View Technical Specs
          </button>
        </div>
      </div>

      {/* Bento Grid Content */}
      <div className="lp-bento-grid">
        
        {/* The Problem vs Solution */}
        <div className="lp-widget span-12 glass">
          <div className="lp-widget-header">
            <LockKeyhole />
            <h3>The Sovereign Imperative</h3>
          </div>
          <div style={{display: 'flex', gap: '32px'}}>
            <div style={{flex: 1}}>
              <b style={{color: '#E53E3E', fontSize: '14px', textTransform: 'uppercase'}}>The Pain</b>
              <p style={{marginTop: '8px'}}>Your data is too sensitive for public AI models. Your team is stuck doing routine work manually due to security constraints.</p>
            </div>
            <div style={{width: '1px', background: 'rgba(0,0,0,0.1)'}}></div>
            <div style={{flex: 1}}>
              <b style={{color: '#38A169', fontSize: '14px', textTransform: 'uppercase'}}>The Solution</b>
              <p style={{marginTop: '8px'}}>OmniVault AI brings the power of state-of-the-art open-weight models directly to your premises. No APIs. No data leaks. Complete sovereign control.</p>
            </div>
          </div>
        </div>

        {/* Core Features */}
        <div id="features" className="lp-widget span-12 glass">
          <div className="lp-widget-header">
            <BrainCircuit />
            <h3>Core Capabilities</h3>
          </div>
          <p>Uncompromising intelligence engineered for on-premise deployment.</p>
          
          <div className="lp-features-grid">
            <div className="lp-feature-card">
              <Lock size={24} color="var(--lp-accent)" />
              <h4>100% Air-Gapped</h4>
              <p>Guaranteed zero data exfiltration. Prove it with your own network monitors.</p>
            </div>
            <div className="lp-feature-card">
              <Network size={24} color="var(--lp-accent)" />
              <h4>Dynamic Model Routing</h4>
              <p>Automatically selects the best open-weight model (Llama-3, Qwen-VL, DeepSeek) for the specific task at hand.</p>
            </div>
            <div className="lp-feature-card">
              <Cog size={24} color="var(--lp-accent)" />
              <h4>True Agentic Execution</h4>
              <p>It doesn’t just chat. It plans, uses a secure Python sandbox, and iterates until the job is done.</p>
            </div>
            <div className="lp-feature-card">
              <FileText size={24} color="var(--lp-accent)" />
              <h4>Real Deliverables</h4>
              <p>Outputs ready-to-use Word documents, Excel spreadsheets, and working code.</p>
            </div>
          </div>
        </div>

        {/* Interactive Use-Cases */}
        <div id="use-cases" className="lp-widget span-8 glass">
          <div className="lp-widget-header">
            <Workflow />
            <h3>Interactive Use-Cases</h3>
          </div>
          <p style={{marginBottom: '20px'}}>See how OmniVault AI transforms secure workflows.</p>
          
          <div className="lp-tabs">
            {tabs.map((tab, idx) => (
              <button 
                key={idx} 
                className={`lp-tab ${activeTab === idx ? 'active' : ''}`}
                onClick={() => setActiveTab(idx)}
              >
                {tab.title}
              </button>
            ))}
          </div>
          <div className="lp-tab-content">
            <p><strong>{tabs[activeTab].title}:</strong> {tabs[activeTab].content}</p>
          </div>
        </div>

        {/* Technical Specs & Hardware Section */}
        <div id="specs" className="lp-widget span-4 glass">
          <div className="lp-widget-header">
            <Server />
            <h3>Technical Specs</h3>
          </div>
          <h4 style={{margin: '0 0 12px', fontSize: '16px', color: 'var(--lp-primary)'}}>Enterprise Power on Accessible Hardware.</h4>
          <p>Designed to run efficiently. Deploy OmniVault AI on a single workstation with a mid-range GPU (e.g., RTX 4090/A6000).</p>
          <div style={{marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--lp-accent)'}}>
            <Cpu size={16}/> Future-proof plug-and-play architecture
          </div>
        </div>

      </div>

      {/* Trust & Compliance Banner */}
      <div className="lp-trust">
        <span style={{fontSize: '14px', fontWeight: '600', color: 'var(--lp-text)'}}>Built for strict compliance:</span>
        <div className="lp-badge"><Lock size={16}/> Defense-grade Security</div>
        <div className="lp-badge"><CheckCircle2 size={16}/> ISO 27001 Ready</div>
        <div className="lp-badge"><Server size={16}/> 100% On-Premise Guarantee</div>
      </div>

      {/* Final CTA & Footer */}
      <div className="lp-footer">
        <div>
          <h2 style={{fontSize: '24px', margin: '0 0 16px', color: 'white', textShadow: '0 2px 4px rgba(0,0,0,0.5)'}}>Ready to automate your secure workflows?</h2>
          <button className="lp-btn primary" onClick={onEnterApp}>
            Schedule a Deployment Consultation
          </button>
        </div>
        
        <div className="lp-footer-links">
          <a href="#">Documentation</a>
          <a href="#">Architecture Whitepaper</a>
          <a href="#">Contact Sales</a>
          <a href="#">Privacy Policy</a>
        </div>
      </div>
    </div>
  );
}
