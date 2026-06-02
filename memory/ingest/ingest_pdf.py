def ingest_pdf(path, memory):
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(path)

        for page in reader.pages:
            text = page.extract_text()
            if text:
                memory.vector_store.add(text, {"source": path})

    except ModuleNotFoundError:
        print(
            "erro ingest pdf: módulo PyPDF2 não encontrado. Instale com 'pip install PyPDF2'."
        )
    except Exception as e:
        print("erro ingest pdf:", e)
