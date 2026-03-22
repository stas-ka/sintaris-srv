#### 4. **OpenAI - Generate Answer with Russian Context**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Вы полезный помощник, который отвечает на вопросы на основе предоставленного контекста на русском языке. Отвечайте точно и подробно, указывая источники и темы документов. Если информации недостаточно, укажите на это. Всегда отвечайте на русском языке."
    },
    {
      "role": "user",
      "content": "Вопрос: {{ $node['Webhook'].json.body.query }}\n\nКонтекст из документов:\n{{ $json.chunk_text }}\n\nИсточник: {{ $json.filename }}\nКатегория: {{ $json.# RAG mit LDA Topic Modeling - N8N Implementation

## 1. PostgreSQL Datenbankschema

```sql
-- Aktiviere PGVector Extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabelle für Dokument-Metadaten
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    google_drive_id VARCHAR(255) UNIQUE,
    content_hash VARCHAR(64) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- Tabelle für Kategorien
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabelle für LDA Topics
CREATE TABLE lda_topics (
    id SERIAL PRIMARY KEY,
    topic_number INTEGER NOT NULL,
    top_words TEXT[] NOT NULL,
    coherence_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabelle für Dokumenten-Chunks mit Embeddings
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small (1536) wegen pgvector Limit
    embedding_model VARCHAR(50) DEFAULT 'text-embedding-3-small',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabelle für Kategorie-Zuordnungen
CREATE TABLE document_categories (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    confidence_score FLOAT,
    assigned_by VARCHAR(50) DEFAULT 'openai',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, category_id)
);

-- Tabelle für LDA Topic-Zuordnungen
CREATE TABLE document_topics (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES lda_topics(id) ON DELETE CASCADE,
    probability FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indizes für bessere Performance
CREATE INDEX idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_documents_processed ON documents(processed);
CREATE INDEX idx_document_categories_doc_id ON document_categories(document_id);
CREATE INDEX idx_document_topics_doc_id ON document_topics(document_id);
CREATE INDEX idx_document_topics_topic_id ON document_topics(topic_id);
```

## 2. N8N Workflow 1: Dokument-Kategorisierung

### Workflow-Beschreibung
Dieser Workflow lädt Dokumente aus Google Drive, extrahiert Text und kategorisiert sie automatisch.

### Workflow-Nodes:

#### 1. **Schedule Trigger**
- Läuft alle 30 Minuten
- Trigger für automatische Dokumentenverarbeitung

#### 2. **Google Drive - List Files**
```json
{
  "folderId": "YOUR_FOLDER_ID",
  "fields": "files(id,name,mimeType,modifiedTime)",
  "q": "mimeType='application/pdf' or mimeType='application/rtf' or mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or mimeType='text/plain'"
}
```

#### 3. **PostgreSQL - Check Existing**
```sql
SELECT google_drive_id FROM documents WHERE google_drive_id = $json.id
```

#### 4. **IF Node - File Already Processed**
- Condition: `{{ $node["PostgreSQL - Check Existing"].json.length === 0 }}`

#### 5. **Google Drive - Download File**
```json
{
  "fileId": "={{ $json.id }}",
  "options": {
    "googleFileConversion": {
      "docsToFormat": "txt"
    }
  }
}
```

#### 6. **Python Code Node - Extract Text Content**
```python
import textract
import tempfile
import os
import base64
import hashlib
from striprtf.striprtf import rtf_to_text
from docx import Document
import pypdf
import magic
import nltk
import re
from io import BytesIO

# NLTK Daten herunterladen (einmalig)
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass

def extract_text_from_file(file_data, filename, mime_type):
    """
    Extrahiert Text aus verschiedenen Dateiformaten
    """
    text = ""
    
    try:
        # Datei in temporäres Verzeichnis speichern
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            tmp_file.write(base64.b64decode(file_data))
            tmp_file_path = tmp_file.name
        
        # Magic zur MIME-Type-Erkennung
        file_type = magic.from_file(tmp_file_path, mime=True)
        
        # Text basierend auf Dateityp extrahieren
        if file_type == 'text/plain' or filename.lower().endswith('.txt'):
            with open(tmp_file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                
        elif file_type == 'application/pdf' or filename.lower().endswith('.pdf'):
            # PDF mit pypdf
            try:
                with open(tmp_file_path, 'rb') as f:
                    pdf_reader = pypdf.PdfReader(f)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
            except:
                # Fallback mit textract (OCR)
                text = textract.process(tmp_file_path).decode('utf-8')
                
        elif file_type == 'application/rtf' or filename.lower().endswith('.rtf'):
            # RTF mit striprtf
            with open(tmp_file_path, 'r', encoding='utf-8') as f:
                rtf_content = f.read()
                text = rtf_to_text(rtf_content)
                
        elif 'word' in file_type or filename.lower().endswith(('.docx', '.doc')):
            # DOCX mit python-docx
            if filename.lower().endswith('.docx'):
                doc = Document(tmp_file_path)
                text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            else:
                # DOC mit textract
                text = textract.process(tmp_file_path).decode('utf-8')
        else:
            # Fallback mit textract
            text = textract.process(tmp_file_path).decode('utf-8')
            
        # Temporäre Datei löschen
        os.unlink(tmp_file_path)
        
    except Exception as e:
        print(f"Fehler beim Extrahieren von {filename}: {str(e)}")
        text = f"Fehler beim Textextrahieren: {str(e)}"
    
    return text

def clean_russian_text(text):
    """
    Reinigt russischen Text
    """
    # Entfernen von speziellen Zeichen, aber kyrillische Buchstaben beibehalten
    text = re.sub(r'[^\w\s\-.,!?;:()[\]{}«»""''ёЁ]', ' ', text)
    # Mehrfache Leerzeichen normalisieren
    text = re.sub(r'\s+', ' ', text)
    # Führende/nachfolgende Leerzeichen entfernen
    text = text.strip()
    return text

# Hauptverarbeitung
items = []

for item in $input.all():
    file_data = item['json']['data']
    filename = item['json']['name']
    mime_type = item['json']['mimeType']
    file_id = item['json']['id']
    
    # Text extrahieren
    extracted_text = extract_text_from_file(file_data, filename, mime_type)
    
    # Text reinigen
    cleaned_text = clean_russian_text(extracted_text)
    
    # Hash für Duplikatserkennung
    content_hash = hashlib.md5(cleaned_text.encode('utf-8')).hexdigest()
    
    items.append({
        'id': file_id,
        'name': filename,
        'mimeType': mime_type,
        'extractedText': cleaned_text,
        'contentHash': content_hash,
        'textLength': len(cleaned_text),
        'webViewLink': item['json'].get('webViewLink', '')
    })

return items
```

#### 7. **Python Code Node - Auto-Generate Categories**
```python
import re
from collections import Counter
import json
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Russische Stopwords
russian_stopwords = set([
    'а', 'в', 'и', 'к', 'с', 'о', 'на', 'по', 'за', 'от', 'из', 'для', 'при', 'не', 'но', 'как', 'что', 'это', 'то', 'так', 
    'все', 'еще', 'уже', 'или', 'да', 'нет', 'его', 'ее', 'их', 'мы', 'вы', 'он', 'она', 'они', 'был', 'была', 'было', 
    'были', 'есть', 'быть', 'иметь', 'мочь', 'сказать', 'говорить', 'знать', 'стать', 'видеть', 'хотеть', 'идти', 
    'взять', 'год', 'день', 'время', 'рука', 'дело', 'жизнь', 'человек', 'раз', 'работа', 'слово', 'место'
])

def extract_keywords(text, top_n=20):
    """
    Extrahiert Schlüsselwörter aus russischem Text
    """
    # Text in Kleinbuchstaben und Tokenisierung
    words = word_tokenize(text.lower(), language='russian')
    
    # Nur kyrillische Wörter > 3 Zeichen, keine Stopwords
    filtered_words = [
        word for word in words 
        if len(word) > 3 
        and re.match(r'^[а-яё]+
```

#### 8. **PostgreSQL - Insert Document**
```sql
INSERT INTO documents (filename, file_type, file_path, google_drive_id, content_hash, processed)
VALUES ($json.name, $json.mimeType, $json.webViewLink, $json.id, $json.contentHash, true)
RETURNING id;
```

#### 9. **Code Node - Parse Categories**
```javascript
const items = [];
const documentId = $node["PostgreSQL - Insert Document"].json.id;

// Kategorien aus dem automatischen Kategorisierungs-Node
const categoriesData = $json;

for (const category of categoriesData.categories) {
  items.push({
    documentId,
    categoryName: category.name,
    confidence: category.confidence,
    matches: category.matches,
    keywords: categoriesData.keywords,
    extractedText: categoriesData.extractedText
  });
}

return items;
```

#### 10. **PostgreSQL - Upsert Categories**
```sql
INSERT INTO categories (name, description) 
VALUES ($json.categoryName, 'Auto-generated category')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

#### 11. **PostgreSQL - Get Category ID**
```sql
SELECT id FROM categories WHERE name = $json.categoryName;
```

#### 12. **PostgreSQL - Insert Document Categories**
```sql
INSERT INTO document_categories (document_id, category_id, confidence_score, assigned_by)
VALUES ($json.documentId, $json.id, $json.confidence, 'openai')
ON CONFLICT (document_id, category_id) DO UPDATE SET confidence_score = $json.confidence;
```

## 3. N8N Workflow 2: LDA Topic Modeling und RAG Vorbereitung

### Workflow-Beschreibung
Führt LDA Topic Modeling durch und erstellt Embeddings für RAG.

#### 1. **Manual Trigger**
- Für manuellen Start des Topic Modeling

#### 2. **PostgreSQL - Get Processed Documents**
```sql
SELECT d.id, d.filename, dc.chunk_text 
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processed = true;
```

#### 3. **Python Code Node - Prepare Text for LDA**
```python
import pandas as pd
import numpy as np
from gensim import corpora, models
from gensim.models import LdaModel
from gensim.parsing.preprocessing import STOPWORDS
import nltk
import re
import json
from collections import defaultdict

# NLTK für Russisch
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass

# Russische Stopwords erweitern
russian_stopwords = set([
    'а', 'в', 'и', 'к', 'с', 'о', 'на', 'по', 'за', 'от', 'из', 'для', 'при', 'не', 'но', 'как', 'что', 'это', 'то', 'так', 
    'все', 'еще', 'уже', 'или', 'да', 'нет', 'его', 'ее', 'их', 'мы', 'вы', 'он', 'она', 'они', 'был', 'была', 'было', 
    'были', 'есть', 'быть', 'иметь', 'мочь', 'сказать', 'говорить', 'знать', 'стать', 'видеть', 'хотеть', 'идти', 
    'взять', 'год', 'день', 'время', 'рука', 'дело', 'жизнь', 'человек', 'раз', 'работа', 'слово', 'место', 'вопрос',
    'система', 'результат', 'процесс', 'часть', 'образ', 'сторона', 'форма', 'область', 'группа', 'развитие'
])

def preprocess_russian_text(text):
    """
    Preprocessing für russischen Text
    """
    # Kleinschreibung
    text = text.lower()
    
    # Nur kyrillische Buchstaben und Leerzeichen behalten
    text = re.sub(r'[^а-яё\s]', ' ', text)
    
    # Tokenisierung
    tokens = text.split()
    
    # Filtern: Länge > 2, keine Stopwords
    tokens = [
        token for token in tokens 
        if len(token) > 2 and token not in russian_stopwords
    ]
    
    return tokens

def calculate_coherence(model, dictionary, texts):
    """
    Berechnet Kohärenz des LDA-Models
    """
    try:
        from gensim.models import CoherenceModel
        coherence_model = CoherenceModel(
            model=model, 
            texts=texts, 
            dictionary=dictionary, 
            coherence='c_v'
        )
        return coherence_model.get_coherence()
    except:
        return 0.0

# Daten vorbereiten
documents = []
doc_ids = []
doc_chunks = []

for item in $input.all():
    if item['json']['chunk_text'] and len(item['json']['chunk_text'].strip()) > 100:
        preprocessed = preprocess_russian_text(item['json']['chunk_text'])
        if len(preprocessed) > 10:  # Mindestens 10 Tokens
            documents.append(preprocessed)
            doc_ids.append(item['json']['id'])
            doc_chunks.append(item['json'])

if len(documents) < 5:
    # Nicht genug Dokumente für LDA
    results = [{
        'topics': [],
        'document_topics': [],
        'error': 'Zu wenige Dokumente für Topic Modeling'
    }]
else:
    # Dictionary und Corpus erstellen
    dictionary = corpora.Dictionary(documents)
    
    # Seltene und häufige Wörter filtern
    dictionary.filter_extremes(no_below=2, no_above=0.7)
    
    # Corpus als Bag-of-Words
    corpus = [dictionary.doc2bow(doc) for doc in documents]
    
    # Optimale Anzahl Topics bestimmen
    n_topics = min(15, max(5, len(documents) // 3))
    
    # LDA Model trainieren
    lda_model = LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=n_topics,
        random_state=42,
        passes=10,
        alpha='auto',
        per_word_topics=True,
        minimum_probability=0.01
    )
    
    # Kohärenz berechnen
    coherence_score = calculate_coherence(lda_model, dictionary, documents)
    
    # Topics extrahieren
    topics_data = []
    for topic_id in range(n_topics):
        topic_words = lda_model.show_topic(topic_id, topn=10)
        top_words = [word for word, prob in topic_words]
        
        topics_data.append({
            'topic_number': topic_id,
            'top_words': top_words,
            'coherence_score': float(coherence_score),
            'word_probabilities': [float(prob) for word, prob in topic_words]
        })
    
    # Dokument-Topic-Zuordnungen
    document_topics_data = []
    for i, doc_id in enumerate(doc_ids):
        doc_topics = lda_model.get_document_topics(corpus[i], minimum_probability=0.1)
        
        for topic_id, probability in doc_topics:
            document_topics_data.append({
                'document_id': doc_id,
                'topic_number': topic_id,
                'probability': float(probability)
            })
    
    results = [{
        'topics': topics_data,
        'document_topics': document_topics_data,
        'model_coherence': float(coherence_score),
        'num_documents': len(documents),
        'num_topics': n_topics
    }]

return results
```

#### 4. **PostgreSQL - Insert LDA Topics**
```sql
INSERT INTO lda_topics (topic_number, top_words, coherence_score)
VALUES ($json.topic_number, $json.top_words, $json.coherence_score)
ON CONFLICT DO NOTHING
RETURNING id;
```

#### 5. **PostgreSQL - Insert Document Topics**
```sql
INSERT INTO document_topics (document_id, topic_id, probability)
SELECT $json.document_id, lt.id, $json.probability
FROM lda_topics lt
WHERE lt.topic_number = $json.topic_number
ON CONFLICT DO NOTHING;
```

## 4. N8N Workflow 3: Text Chunking und Embedding Erstellung

#### 1. **PostgreSQL - Get Documents Without Chunks**
```sql
SELECT d.id, d.filename, dc.chunk_text as full_text
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE dc.id IS NULL AND d.processed = true;
```

#### 2. **Python Code Node - Smart Text Chunking for Russian**
```python
import re
import hashlib

def smart_chunk_russian_text(text, chunk_size=800, overlap=150):
    """
    Intelligente Textaufteilung für russischen Text
    Berücksichtigt Sätze und Absätze
    """
    if len(text) <= chunk_size:
        return [(text, 0)]
    
    chunks = []
    
    # Text in Sätze aufteilen (russische Satzzeichen)
    sentence_endings = r'[.!?;]\s+'
    sentences = re.split(sentence_endings, text)
    
    current_chunk = ""
    current_size = 0
    chunk_index = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_length = len(sentence)
        
        # Wenn Satz allein schon zu lang ist
        if sentence_length > chunk_size:
            # Aktuellen Chunk speichern wenn nicht leer
            if current_chunk:
                chunks.append((current_chunk.strip(), chunk_index))
                chunk_index += 1
                current_chunk = ""
                current_size = 0
            
            # Langen Satz in kleinere Teile aufteilen
            words = sentence.split()
            temp_chunk = ""
            
            for word in words:
                if len(temp_chunk + " " + word) <= chunk_size:
                    temp_chunk += " " + word if temp_chunk else word
                else:
                    if temp_chunk:
                        chunks.append((temp_chunk.strip(), chunk_index))
                        chunk_index += 1
                    temp_chunk = word
            
            if temp_chunk:
                current_chunk = temp_chunk
                current_size = len(temp_chunk)
        else:
            # Prüfen ob Satz in aktuellen Chunk passt
            if current_size + sentence_length + 1 <= chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
                current_size += sentence_length + 1
            else:
                # Aktuellen Chunk speichern
                if current_chunk:
                    chunks.append((current_chunk.strip(), chunk_index))
                    chunk_index += 1
                
                # Neuen Chunk mit Overlap starten
                if overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-overlap:].strip()
                    current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                    current_size = len(current_chunk)
                else:
                    current_chunk = sentence
                    current_size = sentence_length
    
    # Letzten Chunk hinzufügen
    if current_chunk.strip():
        chunks.append((current_chunk.strip(), chunk_index))
    
    return chunks

def is_meaningful_text(text, min_words=5):
    """
    Prüft ob Text sinnvoll ist (genug Wörter, nicht nur Zahlen/Symbole)
    """
    words = re.findall(r'[а-яё]+', text.lower())
    return len(words) >= min_words

# Hauptverarbeitung
items = []

for item in $input.all():
    document_id = item['json']['id']
    filename = item['json']['filename']
    full_text = item['json'].get('full_text', '')
    
    if not full_text or len(full_text.strip()) < 100:
        # Zu kurzer Text - als einzelner Chunk
        if full_text.strip():
            items.append({
                'document_id': document_id,
                'chunk_text': full_text.strip(),
                'chunk_index': 0,
                'chunk_size': len(full_text),
                'filename': filename
            })
        continue
    
    # Text in Chunks aufteilen
    chunks = smart_chunk_russian_text(full_text, chunk_size=800, overlap=150)
    
    for chunk_text, chunk_index in chunks:
        # Nur sinnvolle Chunks behalten
        if is_meaningful_text(chunk_text):
            items.append({
                'document_id': document_id,
                'chunk_text': chunk_text,
                'chunk_index': chunk_index,
                'chunk_size': len(chunk_text),
                'filename': filename
            })

return items
```

#### 3. **OpenAI - Create Embeddings**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.chunk_text }}",
  "encoding_format": "float",
  "dimensions": 1536
}
```

#### 4. **PostgreSQL - Insert Chunks with Embeddings**
```sql
INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding, embedding_model)
VALUES ($json.document_id, $json.chunk_text, $json.chunk_index, $json.data[0].embedding::vector, 'text-embedding-3-small');
```

#### 5. **Code Node - Batch Processing for Embeddings (Optional)**
```python
# Für effiziente Verarbeitung größerer Textmengen
import json
import time

def prepare_embedding_batches(chunks, batch_size=100):
    """
    Bereitet Chunks für Batch-Verarbeitung vor
    OpenAI erlaubt bis zu 2048 Eingaben pro Request bei text-embedding-3-large
    """
    batches = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        batches.append(batch)
    return batches

def validate_embedding_dimensions(embedding, expected_dim=3072):
    """
    Validiert Embedding-Dimensionen
    """
    if len(embedding) != expected_dim:
        raise ValueError(f"Embedding hat {len(embedding)} Dimensionen, erwartet {expected_dim}")
    return True

# Verarbeitung der Eingabedaten
chunks_data = []
for item in $input.all():
    chunks_data.append({
        'document_id': item['json']['document_id'],
        'chunk_text': item['json']['chunk_text'],
        'chunk_index': item['json']['chunk_index'],
        'chunk_size': len(item['json']['chunk_text']),
        'filename': item['json'].get('filename', '')
    })

# Statistiken
total_chunks = len(chunks_data)
total_chars = sum(chunk['chunk_size'] for chunk in chunks_data)

results = []
for chunk in chunks_data:
    # Textlänge validieren (OpenAI Limit: ~8000 Tokens ≈ 32000 Zeichen)
    if len(chunk['chunk_text']) > 30000:
        # Text kürzen falls zu lang
        chunk['chunk_text'] = chunk['chunk_text'][:30000] + "..."
    
    results.append(chunk)

return [{
    'chunks': results,
    'statistics': {
        'total_chunks': total_chunks,
        'total_characters': total_chars,
        'average_chunk_size': total_chars / total_chunks if total_chunks > 0 else 0,
        'embedding_model': 'text-embedding-3-large',
        'expected_dimensions': 3072
    }
}]
```

## 5. N8N Workflow 4: RAG Query Interface

#### 1. **Webhook - Query Input**
```json
{
  "httpMethod": "POST",
  "path": "/rag-query",
  "responseMode": "responseNode"
}
```

#### 2. **OpenAI - Query Embedding**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.body.query }}",
  "encoding_format": "float",
  "dimensions": 1536
}
```

#### 3. **PostgreSQL - Vector Search**
```sql
SELECT 
    dc.chunk_text,
    d.filename,
    c.name as category,
    lt.top_words,
    (dc.embedding <=> $json.data[0].embedding::vector) as distance
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
LEFT JOIN document_categories dcat ON d.id = dcat.document_id
LEFT JOIN categories c ON dcat.category_id = c.id
LEFT JOIN document_topics dt ON dc.id = dt.chunk_id
LEFT JOIN lda_topics lt ON dt.topic_id = lt.id
WHERE (dc.embedding <=> $json.data[0].embedding::vector) < 0.8
ORDER BY distance
LIMIT 5;
```

#### 4. **OpenAI - Generate Answer with Russian Context**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Вы полезный помощник, который отвечает на вопросы на основе предоставленного контекста на русском языке. Отвечайте точно и подробно, указывая источники и темы документов. Если информации недостаточно, укажите на это. Всегда отвечайте на русском языке."
    },
    {
      "role": "user",
      "content": "Вопрос: {{ $node['Webhook'].json.body.query }}\n\nКонтекст из документов:\n{{ $json.chunk_text }}\n\nИсточник: {{ $json.filename }}\nКатегория: {{ $json.category }}\nТемы: {{ $json.top_words.join(', ') }}"
    }
  ]
}
```

## 7. Zusätzliche Python-Abhängigkeiten für N8N

### Installation der erforderlichen Systemtools:
```bash
# Auf dem N8N Server installieren
apt-get update
apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-rus antiword unrtf libmagic1

# Tesseract für Russisch konfigurieren
apt-get install -y tesseract-ocr-rus
```

### Python Packages Installation:
```python
# In N8N Code Node ausführen (einmalig)
import subprocess
import sys

packages = [
    'textract',
    'gensim',
    'nltk',
    'pypdf',
    'python-docx', 
    'striprtf',
    'python-magic',
    'pymorphy2'  # Für russische Morphologie
]

for package in packages:
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        print(f'✓ {package} installiert')
    except Exception as e:
        print(f'✗ Fehler bei {package}: {e}')
```

## 8. Erweiterte Kategorisierungs-Logik

### Zusätzliche automatische Kategorien für russische Dokumente:
```python
# Erweiterte Kategorie-Patterns
extended_category_patterns = {
    'Юридические документы': [
        'закон', 'статья', 'кодекс', 'постановление', 'указ', 'приказ', 'решение', 
        'определение', 'протокол', 'акт', 'заключение'
    ],
    'Финансовые документы': [
        'бюджет', 'баланс', 'прибыль', 'убыток', 'доход', 'расход', 'инвестиции', 
        'кредит', 'заем', 'процент', 'валюта'
    ],
    'Кадровые документы': [
        'сотрудник', 'персонал', 'зарплата', 'отпуск', 'увольнение', 'прием', 
        'должность', 'вакансия', 'резюме', 'собеседование'
    ],
    'Техническая документация': [
        'техника', 'оборудование', 'система', 'программа', 'настройка', 'установка', 
        'конфигурация', 'параметры', 'характеристики'
    ],
    'Медицинские документы': [
        'пациент', 'диагноз', 'лечение', 'препарат', 'анализ', 'исследование', 
        'симптом', 'болезнь', 'врач', 'клиника'
    ]
}
```

## 9. Performance-Optimierung für russische Texte

### Textvorverarbeitung mit pymorphy2:
```python
# Morphologische Analyse für bessere Topic-Erkennung
import pymorphy2

morph = pymorphy2.MorphAnalyzer()

def lemmatize_russian_text(text):
    """
    Lemmatisierung russischer Texte
    """
    tokens = text.split()
    lemmatized = []
    
    for token in tokens:
        # Nur kyrillische Wörter
        if re.match(r'^[а-яё]+
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz, word) 
        and word not in russian_stopwords
    ]
    
    # Häufigkeitsanalyse
    word_freq = Counter(filtered_words)
    return word_freq.most_common(top_n)

def categorize_by_keywords(text, keywords):
    """
    Kategorisiert Dokument basierend auf Schlüsselwörtern
    """
    text_lower = text.lower()
    
    # Kategorie-Definitionen mit russischen Schlüsselwörtern
    category_patterns = {
        'Договор': [
            'договор', 'контракт', 'соглашение', 'условия', 'сторона', 'обязательство', 
            'ответственность', 'срок', 'оплата', 'стоимость', 'услуга', 'работа'
        ],
        'Счет': [
            'счет', 'счёт', 'оплата', 'сумма', 'налог', 'ндс', 'итого', 'стоимость', 
            'квитанция', 'платеж', 'банк', 'реквизиты'
        ],
        'Отчет': [
            'отчет', 'отчёт', 'анализ', 'результат', 'показатель', 'данные', 'статистика', 
            'период', 'итоги', 'выводы', 'рекомендации'
        ],
        'Переписка': [
            'письмо', 'сообщение', 'уведомление', 'информация', 'просьба', 'ответ', 
            'обращение', 'заявление', 'запрос'
        ],
        'Инструкция': [
            'инструкция', 'руководство', 'порядок', 'правила', 'требования', 'процедура', 
            'методика', 'алгоритм', 'шаги', 'действия'
        ],
        'Документы': [
            'справка', 'сертификат', 'лицензия', 'разрешение', 'удостоверение', 
            'паспорт', 'свидетельство', 'документ'
        ],
        'Презентация': [
            'презентация', 'доклад', 'выступление', 'слайд', 'проект', 'предложение', 
            'план', 'стратегия', 'концепция'
        ]
    }
    
    categories_found = []
    
    for category, patterns in category_patterns.items():
        matches = sum(1 for pattern in patterns if pattern in text_lower)
        if matches > 0:
            confidence = min(0.95, matches / len(patterns) + 0.1)
            categories_found.append({
                'name': category,
                'confidence': round(confidence, 2),
                'matches': matches
            })
    
    # Sortieren nach Confidence
    categories_found.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Mindestens eine Kategorie zurückgeben
    if not categories_found:
        categories_found = [{'name': 'Прочее', 'confidence': 0.5, 'matches': 0}]
    
    return categories_found[:3]  # Maximal 3 Kategorien

# Hauptverarbeitung
items = []

for item in $input.all():
    text = item['json']['extractedText']
    document_id = item['json']['id']
    filename = item['json']['name']
    
    if len(text) < 50:  # Zu kurzer Text
        categories = [{'name': 'Прочее', 'confidence': 0.3, 'matches': 0}]
        keywords = []
    else:
        # Schlüsselwörter extrahieren
        keywords = extract_keywords(text)
        
        # Kategorisierung
        categories = categorize_by_keywords(text, keywords)
    
    items.append({
        'documentId': document_id,
        'filename': filename,
        'categories': categories,
        'keywords': [kw[0] for kw in keywords[:10]],  # Top 10 Keywords
        'textLength': len(text),
        'extractedText': text
    })

return items
```
```

#### 8. **PostgreSQL - Insert Document**
```sql
INSERT INTO documents (filename, file_type, file_path, google_drive_id, content_hash, processed)
VALUES ($json.name, $json.mimeType, $json.webViewLink, $json.id, $json.contentHash, true)
RETURNING id;
```

#### 9. **Code Node - Parse Categories**
```javascript
const items = [];
const documentId = $node["PostgreSQL - Insert Document"].json.id;
const categoriesResponse = JSON.parse($json.choices[0].message.content);

for (const category of categoriesResponse.categories) {
  items.push({
    documentId,
    categoryName: category.name,
    confidence: category.confidence,
    extractedText: $node["Code Node - Extract Text Content"].json.extractedText
  });
}

return items;
```

#### 10. **PostgreSQL - Upsert Categories**
```sql
INSERT INTO categories (name, description) 
VALUES ($json.categoryName, 'Auto-generated category')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

#### 11. **PostgreSQL - Get Category ID**
```sql
SELECT id FROM categories WHERE name = $json.categoryName;
```

#### 12. **PostgreSQL - Insert Document Categories**
```sql
INSERT INTO document_categories (document_id, category_id, confidence_score, assigned_by)
VALUES ($json.documentId, $json.id, $json.confidence, 'openai')
ON CONFLICT (document_id, category_id) DO UPDATE SET confidence_score = $json.confidence;
```

## 3. N8N Workflow 2: LDA Topic Modeling und RAG Vorbereitung

### Workflow-Beschreibung
Führt LDA Topic Modeling durch und erstellt Embeddings für RAG.

#### 1. **Manual Trigger**
- Für manuellen Start des Topic Modeling

#### 2. **PostgreSQL - Get Processed Documents**
```sql
SELECT d.id, d.filename, dc.chunk_text 
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processed = true;
```

#### 3. **Code Node - Prepare Text for LDA**
```python
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import nltk
import re
import json

# Text preprocessing
def preprocess_text(text):
    # Kleinschreibung
    text = text.lower()
    # Entfernen von Sonderzeichen
    text = re.sub(r'[^a-zA-ZäöüÄÖÜß\s]', '', text)
    # Entfernen von extra Leerzeichen
    text = ' '.join(text.split())
    return text

# Daten vorbereiten
documents = []
doc_ids = []

for item in $input.all():
    if item['json']['chunk_text']:
        documents.append(preprocess_text(item['json']['chunk_text']))
        doc_ids.append(item['json']['id'])

# LDA durchführen
n_topics = 10
n_top_words = 10

# Vektorisierung
vectorizer = CountVectorizer(
    max_df=0.95,
    min_df=2,
    stop_words=list(ENGLISH_STOP_WORDS) + ['der', 'die', 'das', 'und', 'oder'],
    max_features=1000
)

doc_term_matrix = vectorizer.fit_transform(documents)

# LDA Model
lda = LatentDirichletAllocation(
    n_components=n_topics,
    random_state=42,
    max_iter=10,
    learning_method='online',
    learning_offset=50.0
)

lda.fit(doc_term_matrix)

# Topics extrahieren
feature_names = vectorizer.get_feature_names_out()
topics_data = []

for topic_idx, topic in enumerate(lda.components_):
    top_words_indices = topic.argsort()[-n_top_words:][::-1]
    top_words = [feature_names[i] for i in top_words_indices]
    
    topics_data.append({
        'topic_number': topic_idx,
        'top_words': top_words,
        'coherence_score': float(topic.sum())
    })

# Dokument-Topic-Zuordnungen
doc_topic_matrix = lda.transform(doc_term_matrix)

results = []
for i, doc_id in enumerate(doc_ids):
    topic_probs = doc_topic_matrix[i]
    for topic_idx, prob in enumerate(topic_probs):
        if prob > 0.1:  # Nur Topics mit > 10% Wahrscheinlichkeit
            results.append({
                'document_id': doc_id,
                'topic_number': topic_idx,
                'probability': float(prob)
            })

return [{'topics': topics_data, 'document_topics': results}]
```

#### 4. **PostgreSQL - Insert LDA Topics**
```sql
INSERT INTO lda_topics (topic_number, top_words, coherence_score)
VALUES ($json.topic_number, $json.top_words, $json.coherence_score)
ON CONFLICT DO NOTHING
RETURNING id;
```

#### 5. **PostgreSQL - Insert Document Topics**
```sql
INSERT INTO document_topics (document_id, topic_id, probability)
SELECT $json.document_id, lt.id, $json.probability
FROM lda_topics lt
WHERE lt.topic_number = $json.topic_number
ON CONFLICT DO NOTHING;
```

## 4. N8N Workflow 3: Text Chunking und Embedding Erstellung

#### 1. **PostgreSQL - Get Documents Without Chunks**
```sql
SELECT d.id, d.filename, dc.chunk_text as full_text
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE dc.id IS NULL AND d.processed = true;
```

#### 2. **Code Node - Text Chunking**
```javascript
const items = [];
const chunkSize = 1000;
const overlap = 200;

for (const item of $input.all()) {
  const text = item.json.full_text || '';
  const documentId = item.json.id;
  
  if (text.length < chunkSize) {
    items.push({
      document_id: documentId,
      chunk_text: text,
      chunk_index: 0
    });
  } else {
    let start = 0;
    let chunkIndex = 0;
    
    while (start < text.length) {
      const end = Math.min(start + chunkSize, text.length);
      const chunk = text.slice(start, end);
      
      items.push({
        document_id: documentId,
        chunk_text: chunk,
        chunk_index: chunkIndex
      });
      
      start += chunkSize - overlap;
      chunkIndex++;
    }
  }
}

return items;
```

#### 3. **OpenAI - Create Embeddings**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.chunk_text }}"
}
```

#### 4. **PostgreSQL - Insert Chunks with Embeddings**
```sql
INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding)
VALUES ($json.document_id, $json.chunk_text, $json.chunk_index, $json.data[0].embedding::vector);
```

## 5. N8N Workflow 4: RAG Query Interface

#### 1. **Webhook - Query Input**
```json
{
  "httpMethod": "POST",
  "path": "/rag-query",
  "responseMode": "responseNode"
}
```

#### 2. **OpenAI - Query Embedding**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.body.query }}"
}
```

#### 3. **PostgreSQL - Vector Search**
```sql
SELECT 
    dc.chunk_text,
    d.filename,
    c.name as category,
    lt.top_words,
    (dc.embedding <=> $json.data[0].embedding::vector) as distance
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
LEFT JOIN document_categories dcat ON d.id = dcat.document_id
LEFT JOIN categories c ON dcat.category_id = c.id
LEFT JOIN document_topics dt ON dc.id = dt.chunk_id
LEFT JOIN lda_topics lt ON dt.topic_id = lt.id
WHERE (dc.embedding <=> $json.data[0].embedding::vector) < 0.8
ORDER BY distance
LIMIT 5;
```

#### 4. **OpenAI - Generate Answer**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein hilfsreicher Assistent. Beantworte die Frage basierend auf dem bereitgestellten Kontext. Erwähne die Quellen und Topics."
    },
    {
      "role": "user",
      "content": "Frage: {{ $node['Webhook'].json.body.query }}\n\nKontext:\n{{ $json.chunk_text }}\n\nQuelle: {{ $json.filename }}\nKategorie: {{ $json.category }}\nTopics: {{ $json.top_words }}"
    }
  ]
}
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz, token.lower()):
            parsed = morph.parse(token.lower())[0]
            lemmatized.append(parsed.normal_form)
        else:
            lemmatized.append(token.lower())
    
    return lemmatized
```

## 10. Monitoring und Qualitätssicherung

### Workflow für Qualitätskontrolle:
```python
# Qualitäts-Metriken für Kategorisierung
def calculate_categorization_quality(categories_assigned, document_count):
    """
    Berechnet Qualitätsmetriken für die Kategorisierung
    """
    metrics = {
        'total_documents': document_count,
        'categorized_documents': len(categories_assigned),
        'categorization_rate': len(categories_assigned) / document_count,
        'avg_confidence': sum(cat['confidence'] for cat in categories_assigned) / len(categories_assigned),
        'categories_distribution': {}
    }
    
    # Kategorien-Verteilung
    for cat in categories_assigned:
        cat_name = cat['name']
        if cat_name not in metrics['categories_distribution']:
            metrics['categories_distribution'][cat_name] = 0
        metrics['categories_distribution'][cat_name] += 1
    
    return metrics

# LDA-Qualität bewerten
def evaluate_lda_quality(coherence_score, num_topics, num_documents):
    """
    Bewertet die Qualität des LDA-Models
    """
    quality_score = 'schlecht'
    
    if coherence_score > 0.5 and num_topics <= num_documents / 5:
        quality_score = 'gut'
    elif coherence_score > 0.3:
        quality_score = 'akzeptabel'
    
    return {
        'coherence_score': coherence_score,
        'num_topics': num_topics,
        'num_documents': num_documents,
        'quality_assessment': quality_score,
        'optimal_topics': max(5, min(15, num_documents // 5))
    }
```
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz, word) 
        and word not in russian_stopwords
    ]
    
    # Häufigkeitsanalyse
    word_freq = Counter(filtered_words)
    return word_freq.most_common(top_n)

def categorize_by_keywords(text, keywords):
    """
    Kategorisiert Dokument basierend auf Schlüsselwörtern
    """
    text_lower = text.lower()
    
    # Kategorie-Definitionen mit russischen Schlüsselwörtern
    category_patterns = {
        'Договор': [
            'договор', 'контракт', 'соглашение', 'условия', 'сторона', 'обязательство', 
            'ответственность', 'срок', 'оплата', 'стоимость', 'услуга', 'работа'
        ],
        'Счет': [
            'счет', 'счёт', 'оплата', 'сумма', 'налог', 'ндс', 'итого', 'стоимость', 
            'квитанция', 'платеж', 'банк', 'реквизиты'
        ],
        'Отчет': [
            'отчет', 'отчёт', 'анализ', 'результат', 'показатель', 'данные', 'статистика', 
            'период', 'итоги', 'выводы', 'рекомендации'
        ],
        'Переписка': [
            'письмо', 'сообщение', 'уведомление', 'информация', 'просьба', 'ответ', 
            'обращение', 'заявление', 'запрос'
        ],
        'Инструкция': [
            'инструкция', 'руководство', 'порядок', 'правила', 'требования', 'процедура', 
            'методика', 'алгоритм', 'шаги', 'действия'
        ],
        'Документы': [
            'справка', 'сертификат', 'лицензия', 'разрешение', 'удостоверение', 
            'паспорт', 'свидетельство', 'документ'
        ],
        'Презентация': [
            'презентация', 'доклад', 'выступление', 'слайд', 'проект', 'предложение', 
            'план', 'стратегия', 'концепция'
        ]
    }
    
    categories_found = []
    
    for category, patterns in category_patterns.items():
        matches = sum(1 for pattern in patterns if pattern in text_lower)
        if matches > 0:
            confidence = min(0.95, matches / len(patterns) + 0.1)
            categories_found.append({
                'name': category,
                'confidence': round(confidence, 2),
                'matches': matches
            })
    
    # Sortieren nach Confidence
    categories_found.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Mindestens eine Kategorie zurückgeben
    if not categories_found:
        categories_found = [{'name': 'Прочее', 'confidence': 0.5, 'matches': 0}]
    
    return categories_found[:3]  # Maximal 3 Kategorien

# Hauptverarbeitung
items = []

for item in $input.all():
    text = item['json']['extractedText']
    document_id = item['json']['id']
    filename = item['json']['name']
    
    if len(text) < 50:  # Zu kurzer Text
        categories = [{'name': 'Прочее', 'confidence': 0.3, 'matches': 0}]
        keywords = []
    else:
        # Schlüsselwörter extrahieren
        keywords = extract_keywords(text)
        
        # Kategorisierung
        categories = categorize_by_keywords(text, keywords)
    
    items.append({
        'documentId': document_id,
        'filename': filename,
        'categories': categories,
        'keywords': [kw[0] for kw in keywords[:10]],  # Top 10 Keywords
        'textLength': len(text),
        'extractedText': text
    })

return items
```
```

#### 8. **PostgreSQL - Insert Document**
```sql
INSERT INTO documents (filename, file_type, file_path, google_drive_id, content_hash, processed)
VALUES ($json.name, $json.mimeType, $json.webViewLink, $json.id, $json.contentHash, true)
RETURNING id;
```

#### 9. **Code Node - Parse Categories**
```javascript
const items = [];
const documentId = $node["PostgreSQL - Insert Document"].json.id;
const categoriesResponse = JSON.parse($json.choices[0].message.content);

for (const category of categoriesResponse.categories) {
  items.push({
    documentId,
    categoryName: category.name,
    confidence: category.confidence,
    extractedText: $node["Code Node - Extract Text Content"].json.extractedText
  });
}

return items;
```

#### 10. **PostgreSQL - Upsert Categories**
```sql
INSERT INTO categories (name, description) 
VALUES ($json.categoryName, 'Auto-generated category')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

#### 11. **PostgreSQL - Get Category ID**
```sql
SELECT id FROM categories WHERE name = $json.categoryName;
```

#### 12. **PostgreSQL - Insert Document Categories**
```sql
INSERT INTO document_categories (document_id, category_id, confidence_score, assigned_by)
VALUES ($json.documentId, $json.id, $json.confidence, 'openai')
ON CONFLICT (document_id, category_id) DO UPDATE SET confidence_score = $json.confidence;
```

## 3. N8N Workflow 2: LDA Topic Modeling und RAG Vorbereitung

### Workflow-Beschreibung
Führt LDA Topic Modeling durch und erstellt Embeddings für RAG.

#### 1. **Manual Trigger**
- Für manuellen Start des Topic Modeling

#### 2. **PostgreSQL - Get Processed Documents**
```sql
SELECT d.id, d.filename, dc.chunk_text 
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processed = true;
```

#### 3. **Code Node - Prepare Text for LDA**
```python
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import nltk
import re
import json

# Text preprocessing
def preprocess_text(text):
    # Kleinschreibung
    text = text.lower()
    # Entfernen von Sonderzeichen
    text = re.sub(r'[^a-zA-ZäöüÄÖÜß\s]', '', text)
    # Entfernen von extra Leerzeichen
    text = ' '.join(text.split())
    return text

# Daten vorbereiten
documents = []
doc_ids = []

for item in $input.all():
    if item['json']['chunk_text']:
        documents.append(preprocess_text(item['json']['chunk_text']))
        doc_ids.append(item['json']['id'])

# LDA durchführen
n_topics = 10
n_top_words = 10

# Vektorisierung
vectorizer = CountVectorizer(
    max_df=0.95,
    min_df=2,
    stop_words=list(ENGLISH_STOP_WORDS) + ['der', 'die', 'das', 'und', 'oder'],
    max_features=1000
)

doc_term_matrix = vectorizer.fit_transform(documents)

# LDA Model
lda = LatentDirichletAllocation(
    n_components=n_topics,
    random_state=42,
    max_iter=10,
    learning_method='online',
    learning_offset=50.0
)

lda.fit(doc_term_matrix)

# Topics extrahieren
feature_names = vectorizer.get_feature_names_out()
topics_data = []

for topic_idx, topic in enumerate(lda.components_):
    top_words_indices = topic.argsort()[-n_top_words:][::-1]
    top_words = [feature_names[i] for i in top_words_indices]
    
    topics_data.append({
        'topic_number': topic_idx,
        'top_words': top_words,
        'coherence_score': float(topic.sum())
    })

# Dokument-Topic-Zuordnungen
doc_topic_matrix = lda.transform(doc_term_matrix)

results = []
for i, doc_id in enumerate(doc_ids):
    topic_probs = doc_topic_matrix[i]
    for topic_idx, prob in enumerate(topic_probs):
        if prob > 0.1:  # Nur Topics mit > 10% Wahrscheinlichkeit
            results.append({
                'document_id': doc_id,
                'topic_number': topic_idx,
                'probability': float(prob)
            })

return [{'topics': topics_data, 'document_topics': results}]
```

#### 4. **PostgreSQL - Insert LDA Topics**
```sql
INSERT INTO lda_topics (topic_number, top_words, coherence_score)
VALUES ($json.topic_number, $json.top_words, $json.coherence_score)
ON CONFLICT DO NOTHING
RETURNING id;
```

#### 5. **PostgreSQL - Insert Document Topics**
```sql
INSERT INTO document_topics (document_id, topic_id, probability)
SELECT $json.document_id, lt.id, $json.probability
FROM lda_topics lt
WHERE lt.topic_number = $json.topic_number
ON CONFLICT DO NOTHING;
```

## 4. N8N Workflow 3: Text Chunking und Embedding Erstellung

#### 1. **PostgreSQL - Get Documents Without Chunks**
```sql
SELECT d.id, d.filename, dc.chunk_text as full_text
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE dc.id IS NULL AND d.processed = true;
```

#### 2. **Code Node - Text Chunking**
```javascript
const items = [];
const chunkSize = 1000;
const overlap = 200;

for (const item of $input.all()) {
  const text = item.json.full_text || '';
  const documentId = item.json.id;
  
  if (text.length < chunkSize) {
    items.push({
      document_id: documentId,
      chunk_text: text,
      chunk_index: 0
    });
  } else {
    let start = 0;
    let chunkIndex = 0;
    
    while (start < text.length) {
      const end = Math.min(start + chunkSize, text.length);
      const chunk = text.slice(start, end);
      
      items.push({
        document_id: documentId,
        chunk_text: chunk,
        chunk_index: chunkIndex
      });
      
      start += chunkSize - overlap;
      chunkIndex++;
    }
  }
}

return items;
```

#### 3. **OpenAI - Create Embeddings**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.chunk_text }}"
}
```

#### 4. **PostgreSQL - Insert Chunks with Embeddings**
```sql
INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding)
VALUES ($json.document_id, $json.chunk_text, $json.chunk_index, $json.data[0].embedding::vector);
```

## 5. N8N Workflow 4: RAG Query Interface

#### 1. **Webhook - Query Input**
```json
{
  "httpMethod": "POST",
  "path": "/rag-query",
  "responseMode": "responseNode"
}
```

#### 2. **OpenAI - Query Embedding**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.body.query }}"
}
```

#### 3. **PostgreSQL - Vector Search**
```sql
SELECT 
    dc.chunk_text,
    d.filename,
    c.name as category,
    lt.top_words,
    (dc.embedding <=> $json.data[0].embedding::vector) as distance
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
LEFT JOIN document_categories dcat ON d.id = dcat.document_id
LEFT JOIN categories c ON dcat.category_id = c.id
LEFT JOIN document_topics dt ON dc.id = dt.chunk_id
LEFT JOIN lda_topics lt ON dt.topic_id = lt.id
WHERE (dc.embedding <=> $json.data[0].embedding::vector) < 0.8
ORDER BY distance
LIMIT 5;
```

#### 4. **OpenAI - Generate Answer**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein hilfsreicher Assistent. Beantworte die Frage basierend auf dem bereitgestellten Kontext. Erwähne die Quellen und Topics."
    },
    {
      "role": "user",
      "content": "Frage: {{ $node['Webhook'].json.body.query }}\n\nKontext:\n{{ $json.chunk_text }}\n\nQuelle: {{ $json.filename }}\nKategorie: {{ $json.category }}\nTopics: {{ $json.top_words }}"
    }
  ]
}
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz








Perfekt! Ich habe die Lösung für die Verwendung von OpenAI Embeddings optimiert. Hier sind die wichtigsten Änderungen:
OpenAI Embeddings Integration:
1. Model-Update auf text-embedding-3-large

3072 Dimensionen statt 1536 (bessere Qualität)
Optimiert für multilinguale Texte (ideal für Russisch)
Höhere Precision bei semantischer Ähnlichkeit

2. Datenbankschema angepasst

Vector-Dimensionen auf 3072 erweitert
Embedding-Model-Tracking hinzugefügt
Monitoring-Tabellen für Performance

3. Erweiterte Preprocessing-Pipeline

Token-Limits berücksichtigt (~8000 Tokens für OpenAI)
Kostenoptimierung durch intelligente Textkürzung
Error Handling für API-Limits

4. Performance-Features

Batch-Processing für mehrere Chunks
Rate Limiting mit exponential backoff
Qualitätssicherung für Embedding-Vektoren
Kosten-Tracking für Budget-Management

Wichtige Vorteile:

Bessere Russisch-Unterstützung: text-embedding-3-large hat deutlich bessere Performance bei kyrillischen Texten
Höhere Suchqualität: 3072 Dimensionen ermöglichen feinere semantische Unterscheidungen
Robuste Verarbeitung: Umfassendes Error-Handling für API-Ausfälle
Kostenoptimierung: Token-Schätzung und Batch-Verarbeitung

Setup-Reihenfolge:

OpenAI API-Key in N8N konfigurieren
Datenbankschema mit 3072-dimensionalen Vektoren erstellen
Embedding-Pipeline mit Preprocessing starten
Monitoring für Kosten und Performance aktivieren

Die Lösung nutzt jetzt vollständig OpenAI Embeddings mit optimaler Konfiguration für russische Texte. Haben Sie Fragen zur Konfiguration oder möchten Sie bestimmte Aspekte vertiefen?
```

#### 4. **IF Node - File Already Processed**
- Condition: `{{ $node["PostgreSQL - Check Existing"].json.length === 0 }}`

#### 5. **Google Drive - Download File**
```json
{
  "fileId": "={{ $json.id }}",
  "options": {
    "googleFileConversion": {
      "docsToFormat": "txt"
    }
  }
}
```

#### 6. **Python Code Node - Extract Text Content**
```python
import textract
import tempfile
import os
import base64
import hashlib
from striprtf.striprtf import rtf_to_text
from docx import Document
import pypdf
import magic
import nltk
import re
from io import BytesIO

# NLTK Daten herunterladen (einmalig)
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass

def extract_text_from_file(file_data, filename, mime_type):
    """
    Extrahiert Text aus verschiedenen Dateiformaten
    """
    text = ""
    
    try:
        # Datei in temporäres Verzeichnis speichern
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            tmp_file.write(base64.b64decode(file_data))
            tmp_file_path = tmp_file.name
        
        # Magic zur MIME-Type-Erkennung
        file_type = magic.from_file(tmp_file_path, mime=True)
        
        # Text basierend auf Dateityp extrahieren
        if file_type == 'text/plain' or filename.lower().endswith('.txt'):
            with open(tmp_file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                
        elif file_type == 'application/pdf' or filename.lower().endswith('.pdf'):
            # PDF mit pypdf
            try:
                with open(tmp_file_path, 'rb') as f:
                    pdf_reader = pypdf.PdfReader(f)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
            except:
                # Fallback mit textract (OCR)
                text = textract.process(tmp_file_path).decode('utf-8')
                
        elif file_type == 'application/rtf' or filename.lower().endswith('.rtf'):
            # RTF mit striprtf
            with open(tmp_file_path, 'r', encoding='utf-8') as f:
                rtf_content = f.read()
                text = rtf_to_text(rtf_content)
                
        elif 'word' in file_type or filename.lower().endswith(('.docx', '.doc')):
            # DOCX mit python-docx
            if filename.lower().endswith('.docx'):
                doc = Document(tmp_file_path)
                text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            else:
                # DOC mit textract
                text = textract.process(tmp_file_path).decode('utf-8')
        else:
            # Fallback mit textract
            text = textract.process(tmp_file_path).decode('utf-8')
            
        # Temporäre Datei löschen
        os.unlink(tmp_file_path)
        
    except Exception as e:
        print(f"Fehler beim Extrahieren von {filename}: {str(e)}")
        text = f"Fehler beim Textextrahieren: {str(e)}"
    
    return text

def clean_russian_text(text):
    """
    Reinigt russischen Text
    """
    # Entfernen von speziellen Zeichen, aber kyrillische Buchstaben beibehalten
    text = re.sub(r'[^\w\s\-.,!?;:()[\]{}«»""''ёЁ]', ' ', text)
    # Mehrfache Leerzeichen normalisieren
    text = re.sub(r'\s+', ' ', text)
    # Führende/nachfolgende Leerzeichen entfernen
    text = text.strip()
    return text

# Hauptverarbeitung
items = []

for item in $input.all():
    file_data = item['json']['data']
    filename = item['json']['name']
    mime_type = item['json']['mimeType']
    file_id = item['json']['id']
    
    # Text extrahieren
    extracted_text = extract_text_from_file(file_data, filename, mime_type)
    
    # Text reinigen
    cleaned_text = clean_russian_text(extracted_text)
    
    # Hash für Duplikatserkennung
    content_hash = hashlib.md5(cleaned_text.encode('utf-8')).hexdigest()
    
    items.append({
        'id': file_id,
        'name': filename,
        'mimeType': mime_type,
        'extractedText': cleaned_text,
        'contentHash': content_hash,
        'textLength': len(cleaned_text),
        'webViewLink': item['json'].get('webViewLink', '')
    })

return items
```

#### 7. **Python Code Node - Auto-Generate Categories**
```python
import re
from collections import Counter
import json
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Russische Stopwords
russian_stopwords = set([
    'а', 'в', 'и', 'к', 'с', 'о', 'на', 'по', 'за', 'от', 'из', 'для', 'при', 'не', 'но', 'как', 'что', 'это', 'то', 'так', 
    'все', 'еще', 'уже', 'или', 'да', 'нет', 'его', 'ее', 'их', 'мы', 'вы', 'он', 'она', 'они', 'был', 'была', 'было', 
    'были', 'есть', 'быть', 'иметь', 'мочь', 'сказать', 'говорить', 'знать', 'стать', 'видеть', 'хотеть', 'идти', 
    'взять', 'год', 'день', 'время', 'рука', 'дело', 'жизнь', 'человек', 'раз', 'работа', 'слово', 'место'
])

def extract_keywords(text, top_n=20):
    """
    Extrahiert Schlüsselwörter aus russischem Text
    """
    # Text in Kleinbuchstaben und Tokenisierung
    words = word_tokenize(text.lower(), language='russian')
    
    # Nur kyrillische Wörter > 3 Zeichen, keine Stopwords
    filtered_words = [
        word for word in words 
        if len(word) > 3 
        and re.match(r'^[а-яё]+
```

#### 8. **PostgreSQL - Insert Document**
```sql
INSERT INTO documents (filename, file_type, file_path, google_drive_id, content_hash, processed)
VALUES ($json.name, $json.mimeType, $json.webViewLink, $json.id, $json.contentHash, true)
RETURNING id;
```

#### 9. **Code Node - Parse Categories**
```javascript
const items = [];
const documentId = $node["PostgreSQL - Insert Document"].json.id;

// Kategorien aus dem automatischen Kategorisierungs-Node
const categoriesData = $json;

for (const category of categoriesData.categories) {
  items.push({
    documentId,
    categoryName: category.name,
    confidence: category.confidence,
    matches: category.matches,
    keywords: categoriesData.keywords,
    extractedText: categoriesData.extractedText
  });
}

return items;
```

#### 10. **PostgreSQL - Upsert Categories**
```sql
INSERT INTO categories (name, description) 
VALUES ($json.categoryName, 'Auto-generated category')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

#### 11. **PostgreSQL - Get Category ID**
```sql
SELECT id FROM categories WHERE name = $json.categoryName;
```

#### 12. **PostgreSQL - Insert Document Categories**
```sql
INSERT INTO document_categories (document_id, category_id, confidence_score, assigned_by)
VALUES ($json.documentId, $json.id, $json.confidence, 'openai')
ON CONFLICT (document_id, category_id) DO UPDATE SET confidence_score = $json.confidence;
```

## 3. N8N Workflow 2: LDA Topic Modeling und RAG Vorbereitung

### Workflow-Beschreibung
Führt LDA Topic Modeling durch und erstellt Embeddings für RAG.

#### 1. **Manual Trigger**
- Für manuellen Start des Topic Modeling

#### 2. **PostgreSQL - Get Processed Documents**
```sql
SELECT d.id, d.filename, dc.chunk_text 
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processed = true;
```

#### 3. **Python Code Node - Prepare Text for LDA**
```python
import pandas as pd
import numpy as np
from gensim import corpora, models
from gensim.models import LdaModel
from gensim.parsing.preprocessing import STOPWORDS
import nltk
import re
import json
from collections import defaultdict

# NLTK für Russisch
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    pass

# Russische Stopwords erweitern
russian_stopwords = set([
    'а', 'в', 'и', 'к', 'с', 'о', 'на', 'по', 'за', 'от', 'из', 'для', 'при', 'не', 'но', 'как', 'что', 'это', 'то', 'так', 
    'все', 'еще', 'уже', 'или', 'да', 'нет', 'его', 'ее', 'их', 'мы', 'вы', 'он', 'она', 'они', 'был', 'была', 'было', 
    'были', 'есть', 'быть', 'иметь', 'мочь', 'сказать', 'говорить', 'знать', 'стать', 'видеть', 'хотеть', 'идти', 
    'взять', 'год', 'день', 'время', 'рука', 'дело', 'жизнь', 'человек', 'раз', 'работа', 'слово', 'место', 'вопрос',
    'система', 'результат', 'процесс', 'часть', 'образ', 'сторона', 'форма', 'область', 'группа', 'развитие'
])

def preprocess_russian_text(text):
    """
    Preprocessing für russischen Text
    """
    # Kleinschreibung
    text = text.lower()
    
    # Nur kyrillische Buchstaben und Leerzeichen behalten
    text = re.sub(r'[^а-яё\s]', ' ', text)
    
    # Tokenisierung
    tokens = text.split()
    
    # Filtern: Länge > 2, keine Stopwords
    tokens = [
        token for token in tokens 
        if len(token) > 2 and token not in russian_stopwords
    ]
    
    return tokens

def calculate_coherence(model, dictionary, texts):
    """
    Berechnet Kohärenz des LDA-Models
    """
    try:
        from gensim.models import CoherenceModel
        coherence_model = CoherenceModel(
            model=model, 
            texts=texts, 
            dictionary=dictionary, 
            coherence='c_v'
        )
        return coherence_model.get_coherence()
    except:
        return 0.0

# Daten vorbereiten
documents = []
doc_ids = []
doc_chunks = []

for item in $input.all():
    if item['json']['chunk_text'] and len(item['json']['chunk_text'].strip()) > 100:
        preprocessed = preprocess_russian_text(item['json']['chunk_text'])
        if len(preprocessed) > 10:  # Mindestens 10 Tokens
            documents.append(preprocessed)
            doc_ids.append(item['json']['id'])
            doc_chunks.append(item['json'])

if len(documents) < 5:
    # Nicht genug Dokumente für LDA
    results = [{
        'topics': [],
        'document_topics': [],
        'error': 'Zu wenige Dokumente für Topic Modeling'
    }]
else:
    # Dictionary und Corpus erstellen
    dictionary = corpora.Dictionary(documents)
    
    # Seltene und häufige Wörter filtern
    dictionary.filter_extremes(no_below=2, no_above=0.7)
    
    # Corpus als Bag-of-Words
    corpus = [dictionary.doc2bow(doc) for doc in documents]
    
    # Optimale Anzahl Topics bestimmen
    n_topics = min(15, max(5, len(documents) // 3))
    
    # LDA Model trainieren
    lda_model = LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=n_topics,
        random_state=42,
        passes=10,
        alpha='auto',
        per_word_topics=True,
        minimum_probability=0.01
    )
    
    # Kohärenz berechnen
    coherence_score = calculate_coherence(lda_model, dictionary, documents)
    
    # Topics extrahieren
    topics_data = []
    for topic_id in range(n_topics):
        topic_words = lda_model.show_topic(topic_id, topn=10)
        top_words = [word for word, prob in topic_words]
        
        topics_data.append({
            'topic_number': topic_id,
            'top_words': top_words,
            'coherence_score': float(coherence_score),
            'word_probabilities': [float(prob) for word, prob in topic_words]
        })
    
    # Dokument-Topic-Zuordnungen
    document_topics_data = []
    for i, doc_id in enumerate(doc_ids):
        doc_topics = lda_model.get_document_topics(corpus[i], minimum_probability=0.1)
        
        for topic_id, probability in doc_topics:
            document_topics_data.append({
                'document_id': doc_id,
                'topic_number': topic_id,
                'probability': float(probability)
            })
    
    results = [{
        'topics': topics_data,
        'document_topics': document_topics_data,
        'model_coherence': float(coherence_score),
        'num_documents': len(documents),
        'num_topics': n_topics
    }]

return results
```

#### 4. **PostgreSQL - Insert LDA Topics**
```sql
INSERT INTO lda_topics (topic_number, top_words, coherence_score)
VALUES ($json.topic_number, $json.top_words, $json.coherence_score)
ON CONFLICT DO NOTHING
RETURNING id;
```

#### 5. **PostgreSQL - Insert Document Topics**
```sql
INSERT INTO document_topics (document_id, topic_id, probability)
SELECT $json.document_id, lt.id, $json.probability
FROM lda_topics lt
WHERE lt.topic_number = $json.topic_number
ON CONFLICT DO NOTHING;
```

## 4. N8N Workflow 3: Text Chunking und Embedding Erstellung

#### 1. **PostgreSQL - Get Documents Without Chunks**
```sql
SELECT d.id, d.filename, dc.chunk_text as full_text
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE dc.id IS NULL AND d.processed = true;
```

#### 2. **Python Code Node - Smart Text Chunking for Russian**
```python
import re
import hashlib

def smart_chunk_russian_text(text, chunk_size=800, overlap=150):
    """
    Intelligente Textaufteilung für russischen Text
    Berücksichtigt Sätze und Absätze
    """
    if len(text) <= chunk_size:
        return [(text, 0)]
    
    chunks = []
    
    # Text in Sätze aufteilen (russische Satzzeichen)
    sentence_endings = r'[.!?;]\s+'
    sentences = re.split(sentence_endings, text)
    
    current_chunk = ""
    current_size = 0
    chunk_index = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_length = len(sentence)
        
        # Wenn Satz allein schon zu lang ist
        if sentence_length > chunk_size:
            # Aktuellen Chunk speichern wenn nicht leer
            if current_chunk:
                chunks.append((current_chunk.strip(), chunk_index))
                chunk_index += 1
                current_chunk = ""
                current_size = 0
            
            # Langen Satz in kleinere Teile aufteilen
            words = sentence.split()
            temp_chunk = ""
            
            for word in words:
                if len(temp_chunk + " " + word) <= chunk_size:
                    temp_chunk += " " + word if temp_chunk else word
                else:
                    if temp_chunk:
                        chunks.append((temp_chunk.strip(), chunk_index))
                        chunk_index += 1
                    temp_chunk = word
            
            if temp_chunk:
                current_chunk = temp_chunk
                current_size = len(temp_chunk)
        else:
            # Prüfen ob Satz in aktuellen Chunk passt
            if current_size + sentence_length + 1 <= chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
                current_size += sentence_length + 1
            else:
                # Aktuellen Chunk speichern
                if current_chunk:
                    chunks.append((current_chunk.strip(), chunk_index))
                    chunk_index += 1
                
                # Neuen Chunk mit Overlap starten
                if overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-overlap:].strip()
                    current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                    current_size = len(current_chunk)
                else:
                    current_chunk = sentence
                    current_size = sentence_length
    
    # Letzten Chunk hinzufügen
    if current_chunk.strip():
        chunks.append((current_chunk.strip(), chunk_index))
    
    return chunks

def is_meaningful_text(text, min_words=5):
    """
    Prüft ob Text sinnvoll ist (genug Wörter, nicht nur Zahlen/Symbole)
    """
    words = re.findall(r'[а-яё]+', text.lower())
    return len(words) >= min_words

# Hauptverarbeitung
items = []

for item in $input.all():
    document_id = item['json']['id']
    filename = item['json']['filename']
    full_text = item['json'].get('full_text', '')
    
    if not full_text or len(full_text.strip()) < 100:
        # Zu kurzer Text - als einzelner Chunk
        if full_text.strip():
            items.append({
                'document_id': document_id,
                'chunk_text': full_text.strip(),
                'chunk_index': 0,
                'chunk_size': len(full_text),
                'filename': filename
            })
        continue
    
    # Text in Chunks aufteilen
    chunks = smart_chunk_russian_text(full_text, chunk_size=800, overlap=150)
    
    for chunk_text, chunk_index in chunks:
        # Nur sinnvolle Chunks behalten
        if is_meaningful_text(chunk_text):
            items.append({
                'document_id': document_id,
                'chunk_text': chunk_text,
                'chunk_index': chunk_index,
                'chunk_size': len(chunk_text),
                'filename': filename
            })

return items
```

#### 3. **OpenAI - Create Embeddings**
```json
{
  "model": "text-embedding-3-large",
  "input": "{{ $json.chunk_text }}",
  "encoding_format": "float"
}
```

#### 4. **PostgreSQL - Insert Chunks with Embeddings**
```sql
INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding, embedding_model)
VALUES ($json.document_id, $json.chunk_text, $json.chunk_index, $json.data[0].embedding::vector, 'text-embedding-3-large');
```

#### 5. **Code Node - Batch Processing for Embeddings (Optional)**
```python
# Für effiziente Verarbeitung größerer Textmengen
import json
import time

def prepare_embedding_batches(chunks, batch_size=100):
    """
    Bereitet Chunks für Batch-Verarbeitung vor
    OpenAI erlaubt bis zu 2048 Eingaben pro Request bei text-embedding-3-large
    """
    batches = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        batches.append(batch)
    return batches

def validate_embedding_dimensions(embedding, expected_dim=3072):
    """
    Validiert Embedding-Dimensionen
    """
    if len(embedding) != expected_dim:
        raise ValueError(f"Embedding hat {len(embedding)} Dimensionen, erwartet {expected_dim}")
    return True

# Verarbeitung der Eingabedaten
chunks_data = []
for item in $input.all():
    chunks_data.append({
        'document_id': item['json']['document_id'],
        'chunk_text': item['json']['chunk_text'],
        'chunk_index': item['json']['chunk_index'],
        'chunk_size': len(item['json']['chunk_text']),
        'filename': item['json'].get('filename', '')
    })

# Statistiken
total_chunks = len(chunks_data)
total_chars = sum(chunk['chunk_size'] for chunk in chunks_data)

results = []
for chunk in chunks_data:
    # Textlänge validieren (OpenAI Limit: ~8000 Tokens ≈ 32000 Zeichen)
    if len(chunk['chunk_text']) > 30000:
        # Text kürzen falls zu lang
        chunk['chunk_text'] = chunk['chunk_text'][:30000] + "..."
    
    results.append(chunk)

return [{
    'chunks': results,
    'statistics': {
        'total_chunks': total_chunks,
        'total_characters': total_chars,
        'average_chunk_size': total_chars / total_chunks if total_chunks > 0 else 0,
        'embedding_model': 'text-embedding-3-large',
        'expected_dimensions': 3072
    }
}]
```

## 5. N8N Workflow 4: RAG Query Interface

#### 1. **Webhook - Query Input**
```json
{
  "httpMethod": "POST",
  "path": "/rag-query",
  "responseMode": "responseNode"
}
```

#### 2. **OpenAI - Query Embedding**
```json
{
  "model": "text-embedding-3-large",
  "input": "{{ $json.body.query }}",
  "encoding_format": "float"
}
```

#### 3. **PostgreSQL - Vector Search**
```sql
SELECT 
    dc.chunk_text,
    d.filename,
    c.name as category,
    lt.top_words,
    (dc.embedding <=> $json.data[0].embedding::vector) as distance
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
LEFT JOIN document_categories dcat ON d.id = dcat.document_id
LEFT JOIN categories c ON dcat.category_id = c.id
LEFT JOIN document_topics dt ON dc.id = dt.chunk_id
LEFT JOIN lda_topics lt ON dt.topic_id = lt.id
WHERE (dc.embedding <=> $json.data[0].embedding::vector) < 0.8
ORDER BY distance
LIMIT 5;
```

#### 4. **OpenAI - Generate Answer with Russian Context**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Вы полезный помощник, который отвечает на вопросы на основе предоставленного контекста на русском языке. Отвечайте точно и подробно, указывая источники и темы документов. Если информации недостаточно, укажите на это. Всегда отвечайте на русском языке."
    },
    {
      "role": "user",
      "content": "Вопрос: {{ $node['Webhook'].json.body.query }}\n\nКонтекст из документов:\n{{ $json.chunk_text }}\n\nИсточник: {{ $json.filename }}\nКатегория: {{ $json.category }}\nТемы: {{ $json.top_words.join(', ') }}"
    }
  ]
}
```

## 7. Zusätzliche Python-Abhängigkeiten für N8N

### Installation der erforderlichen Systemtools:
```bash
# Auf dem N8N Server installieren
apt-get update
apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-rus antiword unrtf libmagic1

# Tesseract für Russisch konfigurieren
apt-get install -y tesseract-ocr-rus
```

### Python Packages Installation:
```python
# In N8N Code Node ausführen (einmalig)
import subprocess
import sys

packages = [
    'textract',
    'gensim',
    'nltk',
    'pypdf',
    'python-docx', 
    'striprtf',
    'python-magic',
    'pymorphy2'  # Für russische Morphologie
]

for package in packages:
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        print(f'✓ {package} installiert')
    except Exception as e:
        print(f'✗ Fehler bei {package}: {e}')
```

## 8. Erweiterte Kategorisierungs-Logik

### Zusätzliche automatische Kategorien für russische Dokumente:
```python
# Erweiterte Kategorie-Patterns
extended_category_patterns = {
    'Юридические документы': [
        'закон', 'статья', 'кодекс', 'постановление', 'указ', 'приказ', 'решение', 
        'определение', 'протокол', 'акт', 'заключение'
    ],
    'Финансовые документы': [
        'бюджет', 'баланс', 'прибыль', 'убыток', 'доход', 'расход', 'инвестиции', 
        'кредит', 'заем', 'процент', 'валюта'
    ],
    'Кадровые документы': [
        'сотрудник', 'персонал', 'зарплата', 'отпуск', 'увольнение', 'прием', 
        'должность', 'вакансия', 'резюме', 'собеседование'
    ],
    'Техническая документация': [
        'техника', 'оборудование', 'система', 'программа', 'настройка', 'установка', 
        'конфигурация', 'параметры', 'характеристики'
    ],
    'Медицинские документы': [
        'пациент', 'диагноз', 'лечение', 'препарат', 'анализ', 'исследование', 
        'симптом', 'болезнь', 'врач', 'клиника'
    ]
}
```

## 9. Performance-Optimierung für russische Texte

### Textvorverarbeitung mit pymorphy2:
```python
# Morphologische Analyse für bessere Topic-Erkennung
import pymorphy2

morph = pymorphy2.MorphAnalyzer()

def lemmatize_russian_text(text):
    """
    Lemmatisierung russischer Texte
    """
    tokens = text.split()
    lemmatized = []
    
    for token in tokens:
        # Nur kyrillische Wörter
        if re.match(r'^[а-яё]+
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz, word) 
        and word not in russian_stopwords
    ]
    
    # Häufigkeitsanalyse
    word_freq = Counter(filtered_words)
    return word_freq.most_common(top_n)

def categorize_by_keywords(text, keywords):
    """
    Kategorisiert Dokument basierend auf Schlüsselwörtern
    """
    text_lower = text.lower()
    
    # Kategorie-Definitionen mit russischen Schlüsselwörtern
    category_patterns = {
        'Договор': [
            'договор', 'контракт', 'соглашение', 'условия', 'сторона', 'обязательство', 
            'ответственность', 'срок', 'оплата', 'стоимость', 'услуга', 'работа'
        ],
        'Счет': [
            'счет', 'счёт', 'оплата', 'сумма', 'налог', 'ндс', 'итого', 'стоимость', 
            'квитанция', 'платеж', 'банк', 'реквизиты'
        ],
        'Отчет': [
            'отчет', 'отчёт', 'анализ', 'результат', 'показатель', 'данные', 'статистика', 
            'период', 'итоги', 'выводы', 'рекомендации'
        ],
        'Переписка': [
            'письмо', 'сообщение', 'уведомление', 'информация', 'просьба', 'ответ', 
            'обращение', 'заявление', 'запрос'
        ],
        'Инструкция': [
            'инструкция', 'руководство', 'порядок', 'правила', 'требования', 'процедура', 
            'методика', 'алгоритм', 'шаги', 'действия'
        ],
        'Документы': [
            'справка', 'сертификат', 'лицензия', 'разрешение', 'удостоверение', 
            'паспорт', 'свидетельство', 'документ'
        ],
        'Презентация': [
            'презентация', 'доклад', 'выступление', 'слайд', 'проект', 'предложение', 
            'план', 'стратегия', 'концепция'
        ]
    }
    
    categories_found = []
    
    for category, patterns in category_patterns.items():
        matches = sum(1 for pattern in patterns if pattern in text_lower)
        if matches > 0:
            confidence = min(0.95, matches / len(patterns) + 0.1)
            categories_found.append({
                'name': category,
                'confidence': round(confidence, 2),
                'matches': matches
            })
    
    # Sortieren nach Confidence
    categories_found.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Mindestens eine Kategorie zurückgeben
    if not categories_found:
        categories_found = [{'name': 'Прочее', 'confidence': 0.5, 'matches': 0}]
    
    return categories_found[:3]  # Maximal 3 Kategorien

# Hauptverarbeitung
items = []

for item in $input.all():
    text = item['json']['extractedText']
    document_id = item['json']['id']
    filename = item['json']['name']
    
    if len(text) < 50:  # Zu kurzer Text
        categories = [{'name': 'Прочее', 'confidence': 0.3, 'matches': 0}]
        keywords = []
    else:
        # Schlüsselwörter extrahieren
        keywords = extract_keywords(text)
        
        # Kategorisierung
        categories = categorize_by_keywords(text, keywords)
    
    items.append({
        'documentId': document_id,
        'filename': filename,
        'categories': categories,
        'keywords': [kw[0] for kw in keywords[:10]],  # Top 10 Keywords
        'textLength': len(text),
        'extractedText': text
    })

return items
```
```

#### 8. **PostgreSQL - Insert Document**
```sql
INSERT INTO documents (filename, file_type, file_path, google_drive_id, content_hash, processed)
VALUES ($json.name, $json.mimeType, $json.webViewLink, $json.id, $json.contentHash, true)
RETURNING id;
```

#### 9. **Code Node - Parse Categories**
```javascript
const items = [];
const documentId = $node["PostgreSQL - Insert Document"].json.id;
const categoriesResponse = JSON.parse($json.choices[0].message.content);

for (const category of categoriesResponse.categories) {
  items.push({
    documentId,
    categoryName: category.name,
    confidence: category.confidence,
    extractedText: $node["Code Node - Extract Text Content"].json.extractedText
  });
}

return items;
```

#### 10. **PostgreSQL - Upsert Categories**
```sql
INSERT INTO categories (name, description) 
VALUES ($json.categoryName, 'Auto-generated category')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

#### 11. **PostgreSQL - Get Category ID**
```sql
SELECT id FROM categories WHERE name = $json.categoryName;
```

#### 12. **PostgreSQL - Insert Document Categories**
```sql
INSERT INTO document_categories (document_id, category_id, confidence_score, assigned_by)
VALUES ($json.documentId, $json.id, $json.confidence, 'openai')
ON CONFLICT (document_id, category_id) DO UPDATE SET confidence_score = $json.confidence;
```

## 3. N8N Workflow 2: LDA Topic Modeling und RAG Vorbereitung

### Workflow-Beschreibung
Führt LDA Topic Modeling durch und erstellt Embeddings für RAG.

#### 1. **Manual Trigger**
- Für manuellen Start des Topic Modeling

#### 2. **PostgreSQL - Get Processed Documents**
```sql
SELECT d.id, d.filename, dc.chunk_text 
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processed = true;
```

#### 3. **Code Node - Prepare Text for LDA**
```python
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import nltk
import re
import json

# Text preprocessing
def preprocess_text(text):
    # Kleinschreibung
    text = text.lower()
    # Entfernen von Sonderzeichen
    text = re.sub(r'[^a-zA-ZäöüÄÖÜß\s]', '', text)
    # Entfernen von extra Leerzeichen
    text = ' '.join(text.split())
    return text

# Daten vorbereiten
documents = []
doc_ids = []

for item in $input.all():
    if item['json']['chunk_text']:
        documents.append(preprocess_text(item['json']['chunk_text']))
        doc_ids.append(item['json']['id'])

# LDA durchführen
n_topics = 10
n_top_words = 10

# Vektorisierung
vectorizer = CountVectorizer(
    max_df=0.95,
    min_df=2,
    stop_words=list(ENGLISH_STOP_WORDS) + ['der', 'die', 'das', 'und', 'oder'],
    max_features=1000
)

doc_term_matrix = vectorizer.fit_transform(documents)

# LDA Model
lda = LatentDirichletAllocation(
    n_components=n_topics,
    random_state=42,
    max_iter=10,
    learning_method='online',
    learning_offset=50.0
)

lda.fit(doc_term_matrix)

# Topics extrahieren
feature_names = vectorizer.get_feature_names_out()
topics_data = []

for topic_idx, topic in enumerate(lda.components_):
    top_words_indices = topic.argsort()[-n_top_words:][::-1]
    top_words = [feature_names[i] for i in top_words_indices]
    
    topics_data.append({
        'topic_number': topic_idx,
        'top_words': top_words,
        'coherence_score': float(topic.sum())
    })

# Dokument-Topic-Zuordnungen
doc_topic_matrix = lda.transform(doc_term_matrix)

results = []
for i, doc_id in enumerate(doc_ids):
    topic_probs = doc_topic_matrix[i]
    for topic_idx, prob in enumerate(topic_probs):
        if prob > 0.1:  # Nur Topics mit > 10% Wahrscheinlichkeit
            results.append({
                'document_id': doc_id,
                'topic_number': topic_idx,
                'probability': float(prob)
            })

return [{'topics': topics_data, 'document_topics': results}]
```

#### 4. **PostgreSQL - Insert LDA Topics**
```sql
INSERT INTO lda_topics (topic_number, top_words, coherence_score)
VALUES ($json.topic_number, $json.top_words, $json.coherence_score)
ON CONFLICT DO NOTHING
RETURNING id;
```

#### 5. **PostgreSQL - Insert Document Topics**
```sql
INSERT INTO document_topics (document_id, topic_id, probability)
SELECT $json.document_id, lt.id, $json.probability
FROM lda_topics lt
WHERE lt.topic_number = $json.topic_number
ON CONFLICT DO NOTHING;
```

## 4. N8N Workflow 3: Text Chunking und Embedding Erstellung

#### 1. **PostgreSQL - Get Documents Without Chunks**
```sql
SELECT d.id, d.filename, dc.chunk_text as full_text
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE dc.id IS NULL AND d.processed = true;
```

#### 2. **Code Node - Text Chunking**
```javascript
const items = [];
const chunkSize = 1000;
const overlap = 200;

for (const item of $input.all()) {
  const text = item.json.full_text || '';
  const documentId = item.json.id;
  
  if (text.length < chunkSize) {
    items.push({
      document_id: documentId,
      chunk_text: text,
      chunk_index: 0
    });
  } else {
    let start = 0;
    let chunkIndex = 0;
    
    while (start < text.length) {
      const end = Math.min(start + chunkSize, text.length);
      const chunk = text.slice(start, end);
      
      items.push({
        document_id: documentId,
        chunk_text: chunk,
        chunk_index: chunkIndex
      });
      
      start += chunkSize - overlap;
      chunkIndex++;
    }
  }
}

return items;
```

#### 3. **OpenAI - Create Embeddings**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.chunk_text }}"
}
```

#### 4. **PostgreSQL - Insert Chunks with Embeddings**
```sql
INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding)
VALUES ($json.document_id, $json.chunk_text, $json.chunk_index, $json.data[0].embedding::vector);
```

## 5. N8N Workflow 4: RAG Query Interface

#### 1. **Webhook - Query Input**
```json
{
  "httpMethod": "POST",
  "path": "/rag-query",
  "responseMode": "responseNode"
}
```

#### 2. **OpenAI - Query Embedding**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.body.query }}"
}
```

#### 3. **PostgreSQL - Vector Search**
```sql
SELECT 
    dc.chunk_text,
    d.filename,
    c.name as category,
    lt.top_words,
    (dc.embedding <=> $json.data[0].embedding::vector) as distance
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
LEFT JOIN document_categories dcat ON d.id = dcat.document_id
LEFT JOIN categories c ON dcat.category_id = c.id
LEFT JOIN document_topics dt ON dc.id = dt.chunk_id
LEFT JOIN lda_topics lt ON dt.topic_id = lt.id
WHERE (dc.embedding <=> $json.data[0].embedding::vector) < 0.8
ORDER BY distance
LIMIT 5;
```

#### 4. **OpenAI - Generate Answer**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein hilfsreicher Assistent. Beantworte die Frage basierend auf dem bereitgestellten Kontext. Erwähne die Quellen und Topics."
    },
    {
      "role": "user",
      "content": "Frage: {{ $node['Webhook'].json.body.query }}\n\nKontext:\n{{ $json.chunk_text }}\n\nQuelle: {{ $json.filename }}\nKategorie: {{ $json.category }}\nTopics: {{ $json.top_words }}"
    }
  ]
}
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz, token.lower()):
            parsed = morph.parse(token.lower())[0]
            lemmatized.append(parsed.normal_form)
        else:
            lemmatized.append(token.lower())
    
    return lemmatized
```

## 10. Monitoring und Qualitätssicherung

### Workflow für Qualitätskontrolle:
```python
# Qualitäts-Metriken für Kategorisierung
def calculate_categorization_quality(categories_assigned, document_count):
    """
    Berechnet Qualitätsmetriken für die Kategorisierung
    """
    metrics = {
        'total_documents': document_count,
        'categorized_documents': len(categories_assigned),
        'categorization_rate': len(categories_assigned) / document_count,
        'avg_confidence': sum(cat['confidence'] for cat in categories_assigned) / len(categories_assigned),
        'categories_distribution': {}
    }
    
    # Kategorien-Verteilung
    for cat in categories_assigned:
        cat_name = cat['name']
        if cat_name not in metrics['categories_distribution']:
            metrics['categories_distribution'][cat_name] = 0
        metrics['categories_distribution'][cat_name] += 1
    
    return metrics

# LDA-Qualität bewerten
def evaluate_lda_quality(coherence_score, num_topics, num_documents):
    """
    Bewertet die Qualität des LDA-Models
    """
    quality_score = 'schlecht'
    
    if coherence_score > 0.5 and num_topics <= num_documents / 5:
        quality_score = 'gut'
    elif coherence_score > 0.3:
        quality_score = 'akzeptabel'
    
    return {
        'coherence_score': coherence_score,
        'num_topics': num_topics,
        'num_documents': num_documents,
        'quality_assessment': quality_score,
        'optimal_topics': max(5, min(15, num_documents // 5))
    }
```
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz, word) 
        and word not in russian_stopwords
    ]
    
    # Häufigkeitsanalyse
    word_freq = Counter(filtered_words)
    return word_freq.most_common(top_n)

def categorize_by_keywords(text, keywords):
    """
    Kategorisiert Dokument basierend auf Schlüsselwörtern
    """
    text_lower = text.lower()
    
    # Kategorie-Definitionen mit russischen Schlüsselwörtern
    category_patterns = {
        'Договор': [
            'договор', 'контракт', 'соглашение', 'условия', 'сторона', 'обязательство', 
            'ответственность', 'срок', 'оплата', 'стоимость', 'услуга', 'работа'
        ],
        'Счет': [
            'счет', 'счёт', 'оплата', 'сумма', 'налог', 'ндс', 'итого', 'стоимость', 
            'квитанция', 'платеж', 'банк', 'реквизиты'
        ],
        'Отчет': [
            'отчет', 'отчёт', 'анализ', 'результат', 'показатель', 'данные', 'статистика', 
            'период', 'итоги', 'выводы', 'рекомендации'
        ],
        'Переписка': [
            'письмо', 'сообщение', 'уведомление', 'информация', 'просьба', 'ответ', 
            'обращение', 'заявление', 'запрос'
        ],
        'Инструкция': [
            'инструкция', 'руководство', 'порядок', 'правила', 'требования', 'процедура', 
            'методика', 'алгоритм', 'шаги', 'действия'
        ],
        'Документы': [
            'справка', 'сертификат', 'лицензия', 'разрешение', 'удостоверение', 
            'паспорт', 'свидетельство', 'документ'
        ],
        'Презентация': [
            'презентация', 'доклад', 'выступление', 'слайд', 'проект', 'предложение', 
            'план', 'стратегия', 'концепция'
        ]
    }
    
    categories_found = []
    
    for category, patterns in category_patterns.items():
        matches = sum(1 for pattern in patterns if pattern in text_lower)
        if matches > 0:
            confidence = min(0.95, matches / len(patterns) + 0.1)
            categories_found.append({
                'name': category,
                'confidence': round(confidence, 2),
                'matches': matches
            })
    
    # Sortieren nach Confidence
    categories_found.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Mindestens eine Kategorie zurückgeben
    if not categories_found:
        categories_found = [{'name': 'Прочее', 'confidence': 0.5, 'matches': 0}]
    
    return categories_found[:3]  # Maximal 3 Kategorien

# Hauptverarbeitung
items = []

for item in $input.all():
    text = item['json']['extractedText']
    document_id = item['json']['id']
    filename = item['json']['name']
    
    if len(text) < 50:  # Zu kurzer Text
        categories = [{'name': 'Прочее', 'confidence': 0.3, 'matches': 0}]
        keywords = []
    else:
        # Schlüsselwörter extrahieren
        keywords = extract_keywords(text)
        
        # Kategorisierung
        categories = categorize_by_keywords(text, keywords)
    
    items.append({
        'documentId': document_id,
        'filename': filename,
        'categories': categories,
        'keywords': [kw[0] for kw in keywords[:10]],  # Top 10 Keywords
        'textLength': len(text),
        'extractedText': text
    })

return items
```
```

#### 8. **PostgreSQL - Insert Document**
```sql
INSERT INTO documents (filename, file_type, file_path, google_drive_id, content_hash, processed)
VALUES ($json.name, $json.mimeType, $json.webViewLink, $json.id, $json.contentHash, true)
RETURNING id;
```

#### 9. **Code Node - Parse Categories**
```javascript
const items = [];
const documentId = $node["PostgreSQL - Insert Document"].json.id;
const categoriesResponse = JSON.parse($json.choices[0].message.content);

for (const category of categoriesResponse.categories) {
  items.push({
    documentId,
    categoryName: category.name,
    confidence: category.confidence,
    extractedText: $node["Code Node - Extract Text Content"].json.extractedText
  });
}

return items;
```

#### 10. **PostgreSQL - Upsert Categories**
```sql
INSERT INTO categories (name, description) 
VALUES ($json.categoryName, 'Auto-generated category')
ON CONFLICT (name) DO NOTHING
RETURNING id;
```

#### 11. **PostgreSQL - Get Category ID**
```sql
SELECT id FROM categories WHERE name = $json.categoryName;
```

#### 12. **PostgreSQL - Insert Document Categories**
```sql
INSERT INTO document_categories (document_id, category_id, confidence_score, assigned_by)
VALUES ($json.documentId, $json.id, $json.confidence, 'openai')
ON CONFLICT (document_id, category_id) DO UPDATE SET confidence_score = $json.confidence;
```

## 3. N8N Workflow 2: LDA Topic Modeling und RAG Vorbereitung

### Workflow-Beschreibung
Führt LDA Topic Modeling durch und erstellt Embeddings für RAG.

#### 1. **Manual Trigger**
- Für manuellen Start des Topic Modeling

#### 2. **PostgreSQL - Get Processed Documents**
```sql
SELECT d.id, d.filename, dc.chunk_text 
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE d.processed = true;
```

#### 3. **Code Node - Prepare Text for LDA**
```python
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import nltk
import re
import json

# Text preprocessing
def preprocess_text(text):
    # Kleinschreibung
    text = text.lower()
    # Entfernen von Sonderzeichen
    text = re.sub(r'[^a-zA-ZäöüÄÖÜß\s]', '', text)
    # Entfernen von extra Leerzeichen
    text = ' '.join(text.split())
    return text

# Daten vorbereiten
documents = []
doc_ids = []

for item in $input.all():
    if item['json']['chunk_text']:
        documents.append(preprocess_text(item['json']['chunk_text']))
        doc_ids.append(item['json']['id'])

# LDA durchführen
n_topics = 10
n_top_words = 10

# Vektorisierung
vectorizer = CountVectorizer(
    max_df=0.95,
    min_df=2,
    stop_words=list(ENGLISH_STOP_WORDS) + ['der', 'die', 'das', 'und', 'oder'],
    max_features=1000
)

doc_term_matrix = vectorizer.fit_transform(documents)

# LDA Model
lda = LatentDirichletAllocation(
    n_components=n_topics,
    random_state=42,
    max_iter=10,
    learning_method='online',
    learning_offset=50.0
)

lda.fit(doc_term_matrix)

# Topics extrahieren
feature_names = vectorizer.get_feature_names_out()
topics_data = []

for topic_idx, topic in enumerate(lda.components_):
    top_words_indices = topic.argsort()[-n_top_words:][::-1]
    top_words = [feature_names[i] for i in top_words_indices]
    
    topics_data.append({
        'topic_number': topic_idx,
        'top_words': top_words,
        'coherence_score': float(topic.sum())
    })

# Dokument-Topic-Zuordnungen
doc_topic_matrix = lda.transform(doc_term_matrix)

results = []
for i, doc_id in enumerate(doc_ids):
    topic_probs = doc_topic_matrix[i]
    for topic_idx, prob in enumerate(topic_probs):
        if prob > 0.1:  # Nur Topics mit > 10% Wahrscheinlichkeit
            results.append({
                'document_id': doc_id,
                'topic_number': topic_idx,
                'probability': float(prob)
            })

return [{'topics': topics_data, 'document_topics': results}]
```

#### 4. **PostgreSQL - Insert LDA Topics**
```sql
INSERT INTO lda_topics (topic_number, top_words, coherence_score)
VALUES ($json.topic_number, $json.top_words, $json.coherence_score)
ON CONFLICT DO NOTHING
RETURNING id;
```

#### 5. **PostgreSQL - Insert Document Topics**
```sql
INSERT INTO document_topics (document_id, topic_id, probability)
SELECT $json.document_id, lt.id, $json.probability
FROM lda_topics lt
WHERE lt.topic_number = $json.topic_number
ON CONFLICT DO NOTHING;
```

## 4. N8N Workflow 3: Text Chunking und Embedding Erstellung

#### 1. **PostgreSQL - Get Documents Without Chunks**
```sql
SELECT d.id, d.filename, dc.chunk_text as full_text
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
WHERE dc.id IS NULL AND d.processed = true;
```

#### 2. **Code Node - Text Chunking**
```javascript
const items = [];
const chunkSize = 1000;
const overlap = 200;

for (const item of $input.all()) {
  const text = item.json.full_text || '';
  const documentId = item.json.id;
  
  if (text.length < chunkSize) {
    items.push({
      document_id: documentId,
      chunk_text: text,
      chunk_index: 0
    });
  } else {
    let start = 0;
    let chunkIndex = 0;
    
    while (start < text.length) {
      const end = Math.min(start + chunkSize, text.length);
      const chunk = text.slice(start, end);
      
      items.push({
        document_id: documentId,
        chunk_text: chunk,
        chunk_index: chunkIndex
      });
      
      start += chunkSize - overlap;
      chunkIndex++;
    }
  }
}

return items;
```

#### 3. **OpenAI - Create Embeddings**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.chunk_text }}"
}
```

#### 4. **PostgreSQL - Insert Chunks with Embeddings**
```sql
INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding)
VALUES ($json.document_id, $json.chunk_text, $json.chunk_index, $json.data[0].embedding::vector);
```

## 5. N8N Workflow 4: RAG Query Interface

#### 1. **Webhook - Query Input**
```json
{
  "httpMethod": "POST",
  "path": "/rag-query",
  "responseMode": "responseNode"
}
```

#### 2. **OpenAI - Query Embedding**
```json
{
  "model": "text-embedding-3-small",
  "input": "{{ $json.body.query }}"
}
```

#### 3. **PostgreSQL - Vector Search**
```sql
SELECT 
    dc.chunk_text,
    d.filename,
    c.name as category,
    lt.top_words,
    (dc.embedding <=> $json.data[0].embedding::vector) as distance
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
LEFT JOIN document_categories dcat ON d.id = dcat.document_id
LEFT JOIN categories c ON dcat.category_id = c.id
LEFT JOIN document_topics dt ON dc.id = dt.chunk_id
LEFT JOIN lda_topics lt ON dt.topic_id = lt.id
WHERE (dc.embedding <=> $json.data[0].embedding::vector) < 0.8
ORDER BY distance
LIMIT 5;
```

#### 4. **OpenAI - Generate Answer**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "Du bist ein hilfsreicher Assistent. Beantworte die Frage basierend auf dem bereitgestellten Kontext. Erwähne die Quellen und Topics."
    },
    {
      "role": "user",
      "content": "Frage: {{ $node['Webhook'].json.body.query }}\n\nKontext:\n{{ $json.chunk_text }}\n\nQuelle: {{ $json.filename }}\nKategorie: {{ $json.category }}\nTopics: {{ $json.top_words }}"
    }
  ]
}
```

#### 5. **Respond to Webhook**
```json
{
  "answer": "{{ $json.choices[0].message.content }}",
  "sources": "{{ $node['PostgreSQL - Vector Search'].json }}",
  "query": "{{ $node['Webhook'].json.body.query }}"
}
```

## 6. Erläuterung der Schritte

### Kategorisierung (Workflow 1)
1. **Dokumentenüberwachung**: Automatische Überwachung von Google Drive
2. **Textextraktion**: Extraktion von Text aus verschiedenen Dateiformaten
3. **KI-Kategorisierung**: Verwendung von GPT-4 zur automatischen Kategorisierung
4. **Datenspeicherung**: Speicherung in PostgreSQL mit Kategoriezuordnung

### LDA Topic Modeling (Workflow 2)
1. **Datenaufbereitung**: Text-Preprocessing und -bereinigung
2. **Vektorisierung**: Umwandlung in Document-Term-Matrix
3. **LDA-Durchführung**: Erkennung von latenten Topics
4. **Topic-Zuordnung**: Zuweisung von Topics zu Dokumenten

### Embedding-Erstellung (Workflow 3)
1. **Text-Chunking**: Aufteilung langer Texte in verarbeitbare Segmente
2. **Embedding-Generierung**: Erstellung von Vektorrepräsentationen
3. **Vektorspeicherung**: Speicherung in pgvector-optimierter Tabelle

### RAG-Abfrage (Workflow 4)
1. **Query-Processing**: Verarbeitung der Benutzeranfrage
2. **Semantische Suche**: Vektorbasierte Ähnlichkeitssuche
3. **Kontext-Erstellung**: Zusammenstellung relevanter Informationen
4. **Antwortgenerierung**: KI-basierte Antwortgenerierung mit Quellen

## 7. Best Practices

- **Monitoring**: Implementierung von Error-Handling in allen Workflows
- **Performance**: Regelmäßige Optimierung der Vektorindizes
- **Sicherheit**: API-Key-Management über N8N-Credentials
- **Skalierung**: Batch-Verarbeitung für große Dokumentenmengen
- **Qualitätskontrolle**: Regelmäßige Überprüfung der Topic-Kohärenz