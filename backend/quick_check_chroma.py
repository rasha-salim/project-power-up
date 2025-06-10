import sys
import chromadb
import os

def main():
    # Get document ID from command line
    if len(sys.argv) < 2:
        print("Usage: python quick_check_chroma.py <document_id>")
        return
        
    document_id = sys.argv[1]
    print(f"Checking ChromaDB for document: {document_id}")
    
    # Get ChromaDB client - use the same settings as your application
    chroma_dir = os.path.join(os.getcwd(), "chromadb")
    print(f"Using ChromaDB directory: {chroma_dir}")
    
    client = chromadb.PersistentClient(path=chroma_dir)
    print(f"ChromaDB client initialized")
    
    # Get the collection
    if "documents" not in [c.name for c in client.list_collections()]:
        print("No 'documents' collection found in ChromaDB!")
        return
        
    collection = client.get_collection("documents")
    print(f"Got 'documents' collection from ChromaDB")
    
    # Query for the document ID in the metadata
    try:
        results = collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"]
        )
        
        if results and len(results["ids"]) > 0:
            print(f"\n===== DOCUMENT FOUND IN CHROMADB =====")
            print(f"Found {len(results['ids'])} chunks for document {document_id}")
            
            # Print first chunk info
            print("\nFirst chunk details:")
            print(f"  ID: {results['ids'][0]}")
            
            # Print sample text from first chunk
            if results['documents'] and len(results['documents']) > 0:
                sample_text = results['documents'][0]
                print(f"\nSample text ({len(sample_text)} chars total):")
                print(f"  {sample_text[:100]}..." if len(sample_text) > 100 else sample_text)
            
            # Print metadata from first chunk
            if results['metadatas'] and len(results['metadatas']) > 0:
                print("\nMetadata:")
                for key, value in results['metadatas'][0].items():
                    print(f"  {key}: {value}")
        else:
            print(f"\n===== DOCUMENT NOT FOUND IN CHROMADB =====")
            print("No chunks found with the given document ID")
            print("The document may not have been properly processed or stored in ChromaDB.")
    
    except Exception as e:
        print(f"Error querying ChromaDB: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
