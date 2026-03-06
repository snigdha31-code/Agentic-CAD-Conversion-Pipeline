# AI-Powered CAD Conversion Platform

A full-stack web application that converts **CAD drawings (DWG / DXF)** into **PDF, PNG, and JPG** using an intelligent processing pipeline with AI-assisted conversion planning and asynchronous background workers.

---

## 🚀 Features

- Upload **DWG / DXF CAD files**
- Convert to **PDF, PNG, or JPG**
- **Asynchronous background processing** for large CAD files
- **AI-assisted conversion planning**
- **Automatic fallback pipelines** for failed conversions
- **Real-time job status tracking**
- **Automated output validation** to detect blank or corrupted files

---

## 🏗 System Architecture

## System Architecture

```text
User Upload
   │
   ▼
React Frontend
   │
   ▼
FastAPI Backend
   │
   ▼
Celery Task Queue
   │
   ▼
LLM Planning Module
   │
   ▼
Conversion Providers
   ├── CloudConvert API
   └── Inkscape (Fallback)
   │
   ▼
Output Validation
   ├── PyMuPDF
   ├── NumPy
   └── Pillow
   │
   ▼
Download Result

```
---

## ⚙️ Tech Stack

**Backend**

FastAPI · Python · Celery · Redis · SQLite · SQLAlchemy

**AI Integration**

LLM (GPT-4o-mini via OpenRouter)

**Conversion Engines**

CloudConvert API · Inkscape

**Validation**

PyMuPDF · pypdf · NumPy · Pillow

**Frontend**

React · Vite

---

## 🔄 Processing Pipeline

1. User uploads CAD file
2. Backend creates a **conversion job**
3. Celery worker processes job asynchronously
4. **LLM planner generates conversion strategy**
5. Conversion executed using available providers
6. Output is validated for blank or corrupted results
7. If validation fails, **fallback pipeline triggers**
8. Final output file becomes available for download

---

## 📦 Key Concepts

- Asynchronous distributed processing
- AI-assisted workflow orchestration
- Multi-stage data pipelines
- Fault-tolerant conversion pipelines
- Automated visual validation

---
