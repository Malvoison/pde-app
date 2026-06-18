# **Persistent Digital Entity (PDE) Architecture Specification**

This specification defines a buildable architecture for a persistent digital entity that maintains state, memory, and a dynamic relationship model across discrete user sessions.

The architecture enforces a strict decoupling of the chat interface (the "mouth") from the persistent identity and state machine (the "mind"). It operates under **Model 2 (Maintenance Model)**: processing is synchronous during interactions, while memory grooming, consolidation, and relationship assessments occur asynchronously.

## **1\. Architectural Topology**

The runtime and offline processing loops are split to isolate synchronous user interactions from resource-intensive analysis. We introduce a **Significance Classifier** at the entry point of the asynchronous pipeline to determine the depth of processing required for extracted experiences.

┌────────────────────────────────────────────────────────────────────────┐  
│                      THE RUNTIME LOOP (Synchronous)                    │  
│                                                                        │  
│   ┌──────────┐      ┌────────────────────┐      ┌──────────────────┐   │  
│   │   User   │ ───\> │ Conversation       │ ───\> │  Prompt Builder  │   │  
│   └──────────┘      │ Interface ("Mouth")│      └──────────────────┘   │  
│        ▲            └────────────────────┘                │            │  
│        │                       │ (Write)                  │ (Read)     │  
│        │                       ▼                          ▼            │  
│   ┌──────────┐      ┌────────────────────┐      ┌──────────────────┐   │  
│   │ Response │ \<─── │   LLM API Engine   │      │ Database Store   │   │  
│   └──────────┘      └────────────────────┘      │ (Tiers 1 \- 5\)    │   │  
└─────────────────────────────────────────────────└────────┬─────────┘───┘  
                                                           │  
                        ┌──────────────────────────────────┘  
                        ▼ (Session ID)  
┌────────────────────────────────────────────────────────────────────────┐  
│                OFFLINE WORKFLOWS (Asynchronous)                        │  
│                                                                        │  
│  ┌──────────────────────┐      ┌───────────────────────────────────┐   │  
│  │ Assessment Pipeline  │ ───\> │ Significance Classifier           │   │  
│  │ (Trigger: Session)   │      └─────────────────┬─────────────────┘   │  
│  └──────────────────────┘                        │                     │  
│                                                  ├─ Low Impact ───\> \[Episodic Memory\]  
│                                                  ├─ Medium Impact ─\> \[Episodic \+ Semantic\]  
│                                                  └─ High Impact ──\> \[Episodic \+ Semantic \+ Life Event\]  
│                                                                        │  
│  ┌──────────────────────┐      ┌───────────────────────────────────┐   │  
│  │    Memory Daemon     │ ───\> │ Multi-Tier Consolidation,         │   │  
│  │ (Trigger: Cron/Batch)│      │ Conflict Search, State Machine    │   │  
│  └──────────────────────┘      └───────────────────────────────────┘   │  
└────────────────────────────────────────────────────────────────────────┘

## **2\. Storage & Schema Design**

All state resides in a unified PostgreSQL instance leveraging the pgvector extension.

The life\_events schema stores state transitions and implements a state-machine model (active, stabilizing, integrated, historical). It isolates conversational impact (gravity\_score) from permanent identity presence (relevance\_score).

\-- Enable the vector extension  
CREATE EXTENSION IF NOT EXISTS vector;

\-- Memory Tier classification  
CREATE TYPE memory\_tier AS ENUM ('episodic', 'semantic');

\-- Interaction status classification  
CREATE TYPE interaction\_quality AS ENUM ('positive', 'neutral', 'negative');

\-- Life Event States  
CREATE TYPE life\_event\_state AS ENUM ('active', 'stabilizing', 'integrated', 'historical');

\-- Tier 1: Raw Events Table (Immutable Event Log)  
CREATE TABLE raw\_events (  
    id BIGSERIAL PRIMARY KEY,  
    session\_id UUID NOT NULL,  
    user\_id UUID NOT NULL,  
    speaker VARCHAR(50) NOT NULL, \-- 'user' or 'entity'  
    content TEXT NOT NULL,  
    metadata JSONB DEFAULT '{}'::jsonb, \-- Model config, token metrics, latency  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT\_TIMESTAMP  
);

CREATE INDEX idx\_raw\_events\_session ON raw\_events(session\_id);  
CREATE INDEX idx\_raw\_events\_user ON raw\_events(user\_id);

\-- Tiers 2 & 3: Core Memories (Vector & Document Store)  
CREATE TABLE core\_memories (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    user\_id UUID NOT NULL,  
    tier memory\_tier NOT NULL,  
    content TEXT NOT NULL,  
    embedding VECTOR(1536) NOT NULL, \-- Structured for openai text-embedding-3-small or equivalent  
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence \>= 0.00 AND confidence \<= 1.00),  
    source\_event\_ids BIGINT\[\], \-- Foreign keys to raw\_events for strict verification  
    last\_accessed\_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT\_TIMESTAMP,  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT\_TIMESTAMP  
);

CREATE INDEX idx\_memories\_vector ON core\_memories USING hnsw (embedding vector\_cosine\_ops);  
CREATE INDEX idx\_memories\_user\_tier ON core\_memories(user\_id, tier);

\-- Tier 4 & Relationship Store (User Entity Profiles)  
CREATE TABLE user\_entities (  
    user\_id UUID PRIMARY KEY,  
    identity\_model JSONB NOT NULL DEFAULT '{}'::jsonb, \-- Core preferences, stable communication values  
    trust\_score NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (trust\_score \>= 0.00 AND trust\_score \<= 1.00),  
    engagement\_score NUMERIC(3,2) NOT NULL DEFAULT 0.50 CHECK (engagement\_score \>= 0.00 AND engagement\_score \<= 1.00),  
    conflict\_history\_score NUMERIC(3,2) NOT NULL DEFAULT 0.00 CHECK (conflict\_history\_score \>= 0.00 AND conflict\_history\_score \<= 1.00),  
    updated\_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT\_TIMESTAMP  
);

\-- Tier 5: Life Events / State Transitions Table (The Situational Gravity Layer)  
CREATE TABLE life\_events (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    user\_id UUID NOT NULL,  
    event\_type VARCHAR(100) NOT NULL, \-- e.g., 'bereavement', 'career\_transition', 'relocation', 'health'  
    description TEXT NOT NULL, \-- Summarized impact statement  
    occurred\_at DATE NOT NULL,  
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence \>= 0.00 AND confidence \<= 1.00),  
    state life\_event\_state NOT NULL DEFAULT 'active',  
      
    \-- Dual Scoring Mechanics  
    gravity\_score NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (gravity\_score \>= 0.00 AND gravity\_score \<= 1.00), \-- Persona/tone modifier weight  
    relevance\_score NUMERIC(3,2) NOT NULL DEFAULT 1.00 CHECK (relevance\_score \>= 0.00 AND relevance\_score \<= 1.00), \-- Long-term recall factor  
      
    source\_event\_ids BIGINT\[\], \-- Traces directly back to Tier 1 evidence  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT\_TIMESTAMP  
);

CREATE INDEX idx\_life\_events\_user\_state ON life\_events(user\_id, state);

## **3\. Dynamic Prompt Assembly Engine**

The Prompt Builder dynamically compiles user state into the system context. High-impact state transitions bypass vector RAG entirely when they are in high-relevance or active states, securing persistent situational awareness.

┌─────────────────────────────────────────────────────────────┐  
│ 1\. SYSTEM IDENTITY & BEHAVIORAL BOUNDARIES                  │  
│ "You are an objective, stable partner... Do not adopt a     │  
│  somber tone, but remain aware of current life events..."   │  
├─────────────────────────────────────────────────────────────┤  
│ 2\. TIER 4 IDENTITY & RELATIONSHIP SCHEMA (JSON Injection)    │  
│ Identity Preferences: { "style": "direct" }                  │  
│ Relationship Metrics: { "trust": 0.92, "conflict": 0.04 }   │  
├─────────────────────────────────────────────────────────────┤  
│ 3\. ACTIVE/STABILIZING LIFE EVENTS (Bypasses Vector Search)   │  
│ \[Active Transition\]: Bereavement                             │  
│ Description: "User's wife died on 2026-03-03. Current       │  
│ gravity: 0.95. Tone must reflect care without being funereal"│  
├─────────────────────────────────────────────────────────────┤  
│ 4\. INTEGRATED LIFE EVENTS (Conditional on Relevance / RAG)  │  
│ \[Integrated Transition\]: Career change (Occurred 2025-05)   │  
│ Description: "User transitioned to system operations."      │  
├─────────────────────────────────────────────────────────────┤  
│ 5\. SEMANTIC & EPISODIC CONTEXT (Vector RAG Search Results)  │  
│ \- \[Semantic Memory\] (Similarity: 0.82): "User likes road    │  
│   trips through the Pacific Northwest."                     │  
├─────────────────────────────────────────────────────────────┤  
│ 6\. RECENT IN-CONTEXT SESSION TRANSCRIPT                      │  
│ User: "Thinking about taking a road trip."                  │  
│ Entity: \[Constructs response aware of bereavement status\]   │  
└─────────────────────────────────────────────────────────────┘

### **Retrieval Logic**

1. **Fetch Profile State:** Query user\_entities for identity\_model and relationship scores.  
2. **Fetch High-Gravity Transitions:** Query life\_events where user\_id \= :user\_id and state IN ('active', 'stabilizing'). These are *always* injected.  
3. **Fetch Historical/Integrated Transitions (Similarity Trigger):** Generate embedding for the incoming message. Run cosine similarity against both core\_memories and life\_events where state IN ('integrated', 'historical'). If similarity ![][image1], retrieve and inject.  
4. **Construct Prompt:** Assemble system prompt blocks. The system knows the user's permanent preferences, their current high-gravity life situation, and any contextual history triggered by similarity.

## **4\. Post-Interaction Assessment Pipeline**

Upon session termination, the pipeline processes the raw transcript. It extracts low-impact facts and analyzes whether current active life events have been reinforced, reacted, or show signs of recovery.

from pydantic import BaseModel, Field  
from typing import List, Optional  
import enum  
import uuid  
import datetime

class ImpactCategory(str, enum.Enum):  
    LOW \= "low"         \# Transient facts, preferences (e.g., "prefers black coffee")  
    MEDIUM \= "medium"   \# Shift in routines, tools (e.g., "adopting Go for system backends")  
    HIGH \= "high"       \# Fundamental structural shift (e.g., "lost job", "spouse passed away")

class ExtractedFact(BaseModel):  
    fact: str \= Field(description="Durable, concrete fact or preference revealed by the user.")  
    confidence: float \= Field(description="Confidence weight score from 0.0 to 1.0.")  
    impact\_assessment: ImpactCategory \= Field(description="Estimated structural impact on user's daily life.")  
    event\_type: Optional\[str\] \= Field(None, description="If High impact, classify (e.g., 'bereavement', 'career', 'health', 'relationship').")  
    occurred\_at: Optional\[datetime.date\] \= Field(None, description="Stated date of event occurrence.")

\# LLM Observer: Emits semantic observations only. Does NOT modify state directly.  
class SessionObservations(BaseModel):  
    event\_id: uuid.UUID \= Field(description="Database UUID of the associated Life Event.")  
    direct\_reference\_to\_life\_event: bool \= Field(description="Did the user explicitly mention or heavily imply the event?")  
    acute\_distress\_detected: bool \= Field(description="Are there semantic signals of high acute distress or mourning?")  
    tone: str \= Field(description="One-word descriptor of tone: e.g., grieving, anxious, reflective, neutral, humorous.")  
    functional\_normalcy\_score: float \= Field(description="Score from 0.0 (debilitated) to 1.0 (full engagement on unrelated topics).")  
    reactivation\_trigger\_detected: bool \= Field(description="Did conversation touch on triggers (anniversaries, legal milestones, acute physical setbacks)?")

def process\_post\_session\_assessment(session\_id: uuid.UUID, user\_id: uuid.UUID):  
    transcript \= db.get\_raw\_events(session\_id)  
    event\_ids \= db.get\_event\_ids(session\_id)  
      
    \# 1\. Fact Extraction and Significance Assessment  
    facts: List\[ExtractedFact\] \= llm\_structured\_output(  
        model="gpt-4o-mini",  
        response\_schema=List\[ExtractedFact\],  
        prompt=f"Extract persistent facts and classify their lifecycle impact:\\n{transcript}"  
    )  
      
    for item in facts:  
        if item.confidence \< 0.80:  
            continue  
              
        if item.impact\_assessment \== ImpactCategory.LOW:  
            db.insert\_tier2\_memory(user\_id, "episodic", item.fact, generate\_embedding(item.fact), item.confidence, event\_ids)  
        elif item.impact\_assessment \== ImpactCategory.MEDIUM:  
            db.insert\_tier2\_memory(user\_id, "episodic", item.fact, generate\_embedding(item.fact), item.confidence, event\_ids)  
            db.insert\_tier3\_memory(user\_id, "semantic", item.fact, generate\_embedding(item.fact), item.confidence, event\_ids)  
        elif item.impact\_assessment \== ImpactCategory.HIGH:  
            \# Check for existing event of this type before establishing a new one  
            existing \= db.find\_active\_life\_event(user\_id, item.event\_type)  
            if not existing:  
                db.insert\_life\_event(  
                    user\_id=user\_id,  
                    event\_type=item.event\_type,  
                    description=item.fact,  
                    occurred\_at=item.occurred\_at or datetime.date.today(),  
                    confidence=item.confidence,  
                    source\_event\_ids=event\_ids  
                )

    \# 2\. Extract Session Observations for Existing Active State Transitions  
    active\_events \= db.get\_active\_and\_stabilizing\_events(user\_id)  
    if active\_events:  
        observations: List\[SessionObservations\] \= llm\_structured\_output(  
            model="gpt-4o-mini",  
            response\_schema=List\[SessionObservations\],  
            prompt=f"Evaluate user interaction metrics regarding current life events {active\_events}:\\n{transcript}"  
        )  
        for obs in observations:  
            db.save\_session\_observations(session\_id, obs)

## **5\. The Memory Daemon State Machine**

The Memory Daemon processes state transitions deterministically. It reads observations saved during sessions, applies temporal constraints, and updates gravity\_score, relevance\_score, and state machine values.

### **State Transition Diagram**

                     ┌───────────────┐  
                     │    Active     │  
                     └───────┬───────┘  
                             │ (Min Time Elapsed AND Low Distress AND Functional)  
                             ▼  
                     ┌───────────────┐  
                     │  Stabilizing  │  
                     └───────┬───────┘  
                             │ (Time Elapsed AND Reflective Tone AND Topic Divergence)  
                             ▼  
                     ┌───────────────┐  
                     │  Integrated   │◄────────────────────────┐  
                     └───────┬───────┘                         │  
                             │ (Extended Inactivity)           │ (Anniversary, Context Trigger,  
                             ▼                                 │  or New Distress Signal)  
                     ┌───────────────┐                         │  
                     │  Historical   ├─────────────────────────┘  
                     └───────────────┘

### **Deterministic State Machine Engine**

The state machine runs execution blocks for active events using a configuration map based on event types:

STATE\_MACHINE\_CONFIG \= {  
    "bereavement": {  
        "active\_min\_days": 60,  
        "stabilizing\_min\_days": 300,  
        "never\_expire\_relevance": True,  
        "base\_decay\_rate": 0.005 \# Slow daily baseline drop  
    },  
    "career\_transition": {  
        "active\_min\_days": 14,  
        "stabilizing\_min\_days": 90,  
        "never\_expire\_relevance": False,  
        "base\_decay\_rate": 0.02  
    },  
    "health\_diagnosis": {  
        "active\_min\_days": 30,  
        "stabilizing\_min\_days": 180,  
        "never\_expire\_relevance": True,  
        "base\_decay\_rate": 0.01  
    },  
    "relationship\_dissolution": {  
        "active\_min\_days": 45,  
        "stabilizing\_min\_days": 365,  
        "never\_expire\_relevance": False,  
        "base\_decay\_rate": 0.01  
    }  
}

#### **Deterministic Calculations (Capped Mechanics)**

During the nightly optimization run, for each active and stabilizing life\_event, compute the updated scores and state transitions:

def update\_life\_event\_states(user\_id: uuid.UUID):  
    events \= db.get\_all\_unresolved\_life\_events(user\_id)  
      
    for event in events:  
        config \= STATE\_MACHINE\_CONFIG.get(event.event\_type, STATE\_MACHINE\_CONFIG\["career\_transition"\])  
        days\_since\_occurrence \= (datetime.date.today() \- event.occurred\_at).days  
          
        \# Get all observations for this event over the last 24h  
        observations \= db.get\_recent\_observations(event.id)  
          
        \# 1\. Compute Gravity Update  
        \# gravity\_score \= previous \- base\_decay(time) \+ reinforcement \- recovery\_signals  
        base\_decay \= config\["base\_decay\_rate"\]  
          
        reinforcement \= 0.0  
        recovery\_signals \= 0.0  
          
        for obs in observations:  
            if obs.direct\_reference\_to\_life\_event:  
                reinforcement \+= 0.05  
            if obs.acute\_distress\_detected:  
                reinforcement \+= 0.10  
            if obs.reactivation\_trigger\_detected:  
                reinforcement \+= 0.15  
                  
            \# Functional normalcy and reflective recovery drops gravity  
            recovery\_signals \+= (obs.functional\_normalcy\_score \* 0.08)  
            if obs.tone in \["reflective", "neutral", "humorous"\]:  
                recovery\_signals \+= 0.05

        \# Apply score caps  
        new\_gravity \= float(event.gravity\_score) \- base\_decay \+ reinforcement \- recovery\_signals  
        event.gravity\_score \= max(0.00, min(1.00, new\_gravity))  
          
        \# 2\. State-Machine Guard Transitions  
        if event.state \== "active":  
            \# Active \-\> Stabilizing transitions require min time AND evidence of functional normalcy  
            if days\_since\_occurrence \>= config\["active\_min\_days"\]:  
                recent\_distress \= any(o.acute\_distress\_detected for o in observations)  
                avg\_normalcy \= sum(o.functional\_normalcy\_score for o in observations) / max(1, len(observations))  
                  
                if not recent\_distress and avg\_normalcy \> 0.60:  
                    event.state \= "stabilizing"  
                    event.gravity\_score \= min(event.gravity\_score, 0.70) \# Cap stabilizing gravity

        elif event.state \== "stabilizing":  
            \# Stabilizing \-\> Integrated transitions require minimum stabilizing duration  
            total\_stabilizing\_duration \= days\_since\_occurrence \- config\["active\_min\_days"\]  
            if total\_stabilizing\_duration \>= config\["stabilizing\_min\_days"\]:  
                direct\_references \= any(o.direct\_reference\_to\_life\_event for o in observations)  
                if not direct\_references:  
                    event.state \= "integrated"  
                    event.gravity\_score \= 0.00  
                    \# For minor events, drop relevance. Bereavement or critical health maintains 1.0 relevance.  
                    if not config\["never\_expire\_relevance"\]:  
                        event.relevance\_score \= 0.50

        elif event.state \== "integrated":  
            \# Integrated \-\> Historical  
            if days\_since\_occurrence \> 365 and not config\["never\_expire\_relevance"\]:  
                event.state \= "historical"  
                event.relevance\_score \= 0.10  
                  
        \# 3\. Handle Reactivation Triggers (E.g. anniversary detected or fresh distress)  
        for obs in observations:  
            if obs.reactivation\_trigger\_detected or (event.state in \["integrated", "historical"\] and obs.acute\_distress\_detected):  
                event.state \= "active"  
                event.gravity\_score \= max(event.gravity\_score, 0.85)  
                event.relevance\_score \= 1.00  
                  
        db.save\_life\_event(event)

## **6\. Structural Controls and Safety Constraints**

1. **Replay Engine and State Rollback:** Because the Raw Event Log (raw\_events) acts as an immutable ledger, any state transition issue or scoring imbalance can be repaired. The developer can wipe the life\_events table, restore parameters to baseline, and replay session observations chronologically to calculate the precise state.  
2. **Supportive Isolation Directive:** System instructions strictly prohibit matching user grief. The Prompt Builder injects context but explicitly constrains output: *"The user is dealing with bereavement \[Gravity: 0.90\]. Provide utility and intellectual companionship. Do not express personal sorrow, run-of-the-mill condolence scripts, or assume the role of an emotional counselor."*  
3. **Traceability Pointers:** Every structural update to life\_events requires direct reference to the parent session\_id or vector ID. If an evaluation is disputed, the operator can fetch the exact textual logs that triggered the transition, preventing hallucinated context from destabilizing the core state.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADoAAAAZCAYAAABggz2wAAADC0lEQVR4Xu2WS2jUUBSGE1qh4gsf49B5ZV4wiCDqiKWuVaiiCFUs2o24qIgbFRR3ghSpG0FHFLWICxGculMUWqyIIFhxVdyIiFJwVXeFbnx8h0nG29NMJqPtyvzwk9z//Dk5J/fmJpYVIUKE/xa5XK7kOM4VeBseSaVSS7VHA18nfAz3uOdzGIvFlosvk8kcYrzDHduFQmE9Wn82m92sUi4uKKIXfpAbSzGcX4Kj+Xx+lfaaoNgyvhn4y4/kG8DWzvGRjsFqYH4u6hBq/W+RSCTS3PQjPOppNLCa8QQ8ZXo18O3D886prQKTL+GY1wjnd+Ek/q8cR+Be5DaVbi4w5zGO0uxQMplcq+OtQhqEMzI7hmyjPZCCveXnB2o4zXU7TU2a47oq+kZPY3xd5Q8Nm3dqEwmewWGY04aw4NprPo1KE/fRv8mDNXUTxLfyLq8xJFsmAL3X0P6p0TrcTaQqlHMdbwa3oUaNztODkE6n9+O/VS6Xl5g6eSroVzm+h1PwDdxiekJDZhUOU+Ar2IVka4+Gu/HI+zSvoVYbldcI/wvYrWPkuEe+C5b7XjLux/edidmurOHh1Lb2G2Eajsfjy/CO+TXUaqP4+/BPsrmt07FSqbTCMjYfHkrKqc3sQ4btf5wtQp4uBd4k0WsKyOq4iUYNNdL9IN9cfM/xj1ghCncn4wv8xKzGdbwp3AQVON5sNj3gHfRryG10Sp6+qfsB3wY4LdfoGNoxYj85nvA0o1Fhp+kPhFN7P+/AJ7IbWyEa9CAbCNf9yBifCYrqQHsqlHNXbpPVYYzrwNfj1H4CBnWMvOclZjZqLN3Az5eHBfnEyDKniLfwoqexFItSCFqfpzE+7jYz773CNyAxacrUBejdsGLuxPgPo8066jOkYWPswjQuCZxWpr4BmNVt5PlMoefgQc4nuMeQWVym9hc0Kx5LrRj0M40aBfLzcdatVx6WfLen4UmJaXMdGHpIeHkh/opMyA5Mw7tp8ID8Fup4EORaatpVLBZX6pgHySm55R6B/7gRIkSIECHC4uA3sjbhk07VFC8AAAAASUVORK5CYII=>