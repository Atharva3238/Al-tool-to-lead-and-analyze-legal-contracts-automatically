# main.py
from graph import build_graph

if __name__ == "__main__":
    app = build_graph()

    result = app.invoke({
        "file_path": "sample_contract.pdf"
    })

    print("Contract Type:", result["contract_type"])
    print("Industry:", result["industry"])

    print("\nRetrieved Clauses:")
    for c in result["clauses"]:
        print("-", c["clause_title"])

    print("\nFINAL CONTRACT ANALYSIS:\n")
    print(result["final_analysis"])

