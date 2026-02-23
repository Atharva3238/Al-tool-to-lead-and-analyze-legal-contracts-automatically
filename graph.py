from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from parser import parse_document
import json
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
from langchain_ollama import OllamaEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage


client = QdrantClient(url="http://localhost:6333")

embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

vectorstore = QdrantVectorStore(
    client=client,
    collection_name="contract_clauses",
    embedding=embeddings
)



llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0
)

classification_prompt = ChatPromptTemplate.from_template("""
You are a legal contract classification system.

Choose contract_type from ONLY the following list:
- General Clauses
- Employment Agreement
- Government Standard (FAR)
- Non-Disclosure Agreement (NDA)

Return ONLY valid JSON:
{{
  "contract_type": "...",
  "industry": "..."
}}

Contract text:
{text}
""")



class ContractState(TypedDict):
    file_path: str
    contract_text: str
    contract_type: Optional[str]
    industry: Optional[str]
    clauses: List[dict]
    analysis_report: Optional[str]
    review_plan: List[str]          
    sections: List[str]             
    modifications: List[dict]       
    final_report: Optional[str] 


def parse_node(state: ContractState):
    text = parse_document(state["file_path"])
    return {"contract_text": text}


def classify_node(state: ContractState):
    prompt = classification_prompt.format_messages(
        text=state["contract_text"]
    )
    response = llm.invoke(prompt)

    result = json.loads(response.content)

    return {
        "contract_type": result["contract_type"],
        "industry": result["industry"]
    }

def retrieve_clauses_node(state: ContractState):
    contract_type = state["contract_type"]
    
    # Convert query to more semantic-friendly terms
    general_query = "general legal provisions"
    specific_query = f"{contract_type} clauses"

    
    # Always fetch general clauses
    general_clauses = vectorstore.similarity_search(
        query=general_query,
        k=3,  # Reduced to avoid getting too many
    )
    
    # Filter general clauses to only get General Clauses type
    filtered_general = [
        c for c in general_clauses 
        if c.metadata.get("contract_type") == "General Clauses"
    ]
    
    # Fetch specific clauses
    specific_clauses = []
    if contract_type in [
        "Employment Agreement",
        "Government Standard (FAR)",
        "Non-Disclosure Agreement (NDA)"
    ]:
        specific_clauses = vectorstore.similarity_search(
            query=specific_query,
            k=5,
        )
        # Filter specific clauses to match the contract type
        specific_clauses = [
            c for c in specific_clauses 
            if c.metadata.get("contract_type") == contract_type
        ]
    
    clauses = filtered_general + specific_clauses
    
    # Debug print to see what's being retrieved
    # print(f"Retrieving clauses for contract type: {contract_type}")
    # print(f"General clauses found: {len(filtered_general)}")
    # print(f"Specific clauses found: {len(specific_clauses)}")
    
    return {
        "clauses": [
            {
                "clause_title": c.metadata.get("clause_title", "Unknown Title"),
                "clause_text": c.page_content,
                "contract_type": c.metadata.get("contract_type")
            }
            for c in clauses
        ]
    }

def analyze_contract_node(state: ContractState):
    llm = ChatOllama(
        model="llama3.1:8b",
        temperature=0
    )

    contract_text = state["contract_text"]
    clauses = state["clauses"]

    # Prepare expected clauses text
    expected_clauses_text = "\n\n".join(
        [
            f"Clause Title: {c['clause_title']}\nClause Text:\n{c['clause_text']}"
            for c in clauses
        ]
    )

    system_prompt = f"""
You are a Legal Contract Analyst.

Your task:
1. Compare the contract text with the EXPECTED CLAUSES.
2. For each clause:
   - Say if it is PRESENT or MISSING.
   - If present, say whether it is adequate or weak.
   - Suggest improvements if needed.
3. Identify important clauses that are completely missing.
4. Provide a short overall assessment and recommendations.

EXPECTED CLAUSES:
{expected_clauses_text}
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Contract to analyze:\n\n{contract_text}")
    ]

    response = llm.invoke(messages)

    return {
        "analysis_report": response.content
    }

def create_review_plan_node(state: ContractState):
    system_prompt = f"""
You are a legal contract review planner.

Create a role-based review plan for the following contract:
- Contract Type: {state['contract_type']}
- Industry: {state['industry']}

Each step must be a specific legal expert role.
Generate 3–5 roles only.
Avoid generic roles.
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Generate the review roles.")
    ]

    result = llm.invoke(messages)

    roles = [
    r.strip("-* ").strip()
    for r in result.content.split("\n")
    if "Role" in r
]


    return {"review_plan": roles}


def execute_step_node(state: ContractState):
    role = state["review_plan"].pop(0)
  

    system_prompt = f"""
You are acting as a {role}.

Review the contract and:
1. Analyze relevant sections
2. Identify issues
3. Suggest up to 3 critical modifications
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["contract_text"])
    ]

    result = llm.invoke(messages)

    section = f"### {role}\n{result.content}"

    return {
        "sections": [section],
        "modifications": []  # optionally parse structured output later
    }


def generate_final_report_node(state):
    report = []

    report.append("# Contract Review Report\n")
    report.append(f"**Contract Type:** {state['contract_type']}")
    report.append(f"**Industry:** {state['industry']}\n")

    if state.get("analysis_report"):
        report.append("## Clause Analysis\n")
        report.append(state["analysis_report"])

    report.append("\n## Expert Reviews\n")
    report.extend(state.get("sections", []))

    return {
        "final_report": "\n\n".join(report)
    }




def build_graph():
    workflow = StateGraph(ContractState)

    workflow.add_node("parse", parse_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("retrieve_clauses", retrieve_clauses_node)
    workflow.add_node("analyze_contract", analyze_contract_node)

    workflow.add_node("create_review_plan", create_review_plan_node)
    workflow.add_node("execute_step", execute_step_node)
    workflow.add_node("generate_final_report", generate_final_report_node)

    workflow.set_entry_point("parse")

    workflow.add_edge("parse", "classify")
    workflow.add_edge("classify", "retrieve_clauses")
    workflow.add_edge("retrieve_clauses", "analyze_contract")
    workflow.add_edge("analyze_contract", "create_review_plan")

    workflow.add_edge("create_review_plan", "execute_step")
    workflow.add_edge("execute_step", "generate_final_report")
    workflow.add_edge("generate_final_report", END)

    return workflow.compile()




graph = build_graph()
