import os
import uuid
import tempfile
import numpy as np
import httpx
from datetime import datetime as dt
from typing import List, Optional
from core.database import db
from services.other.file_service import FileService
from meeting.services.moderation_service import _call_openrouter, TEXT_MODEL, VISION_MODEL
from sentence_transformers import SentenceTransformer
import base64
import asyncio


class DocumentRAGService:
    def __init__(self):
        self.db = db
        self.document_indexes_col = db.document_indexes
        self.document_chunks_col = db.document_chunks
        self.document_ai_messages_col = db.document_ai_messages
        self.embedding_model = None

    def _get_embedding_model(self):
        if self.embedding_model is None:
            if SentenceTransformer is None:
                raise RuntimeError("sentence-transformers chưa được cài đặt")
            self.embedding_model = SentenceTransformer("intfloat/multilingual-e5-small")
        return self.embedding_model

    def _conversation_id(self, user_email: str, document_id: str) -> str:
        return f"{user_email.strip().lower()}:{document_id}"
    
    def _render_pdf_pages_to_images(
        self,
        pdf_path: str,
        output_dir: str,
        max_pages: int = 8,
        zoom: float = 1.5
    ) -> list:
        try:
            import fitz  # PyMuPDF
        except Exception:
            raise RuntimeError("Chưa cài pymupdf. Hãy chạy: pip install pymupdf")

        image_paths = []

        doc = fitz.open(pdf_path)

        try:
            total_pages = min(len(doc), max_pages)

            matrix = fitz.Matrix(zoom, zoom)

            for page_index in range(total_pages):
                page = doc[page_index]
                pix = page.get_pixmap(matrix=matrix, alpha=False)

                image_path = os.path.join(
                    output_dir,
                    f"page_{page_index + 1}.jpg"
                )

                pix.save(image_path)
                image_paths.append(image_path)

        finally:
            doc.close()

        return image_paths
    
    async def _extract_pdf_text_with_vision(
        self,
        pdf_path: str,
        file_name: str,
        tmp_dir: str
    ) -> str:
        import PyPDF2

        text_parts = []

        # 1. Extract text layer như giai đoạn 1
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)

                for idx, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""

                    if page_text.strip():
                        text_parts.append(
                            f"\n\n[Trang {idx + 1} - văn bản trích xuất]\n{page_text.strip()}"
                        )

        except Exception as e:
            print(f"[DOC_RAG][PDF_TEXT] Error: {e}")

        # 2. Render page thành ảnh rồi mô tả bằng vision
        try:
            page_images = self._render_pdf_pages_to_images(
                pdf_path=pdf_path,
                output_dir=tmp_dir,
                max_pages=8,
                zoom=1.5
            )

            labels = [
                f"Trang {idx + 1} của tài liệu {file_name}"
                for idx in range(len(page_images))
            ]

            descriptions = await self._describe_images_limited(
                image_paths=page_images,
                labels=labels,
                max_concurrency=2
            )

            for idx, desc in enumerate(descriptions):
                if desc and desc.strip():
                    text_parts.append(
                        f"\n\n[Trang {idx + 1} - mô tả hình ảnh/page bằng AI vision]\n{desc.strip()}"
                    )

        except Exception as e:
            print(f"[DOC_RAG][PDF_VISION] Error: {e}")

        return "\n".join(text_parts).strip()
    
    async def _extract_docx_text_with_images(
        self,
        docx_path: str,
        file_name: str,
        tmp_dir: str
    ) -> str:
        from docx import Document
        import zipfile

        text_parts = []

        # 1. Text paragraph
        try:
            doc = Document(docx_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            if paragraphs:
                text_parts.append(
                    "\n\n[DOCX - văn bản trích xuất]\n" + "\n".join(paragraphs)
                )

        except Exception as e:
            print(f"[DOC_RAG][DOCX_TEXT] Error: {e}")

        # 2. Extract embedded images từ word/media/*
        image_paths = []

        try:
            with zipfile.ZipFile(docx_path, "r") as z:
                media_files = [
                    name for name in z.namelist()
                    if name.startswith("word/media/")
                    and name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                ]

                for idx, name in enumerate(media_files[:10]):
                    ext = os.path.splitext(name)[1].lower() or ".jpg"
                    image_path = os.path.join(tmp_dir, f"docx_image_{idx + 1}{ext}")

                    with open(image_path, "wb") as f:
                        f.write(z.read(name))

                    image_paths.append(image_path)

        except Exception as e:
            print(f"[DOC_RAG][DOCX_IMAGES] Error: {e}")

        if image_paths:
            labels = [
                f"Ảnh {idx + 1} trong tài liệu DOCX {file_name}"
                for idx in range(len(image_paths))
            ]

            descriptions = await self._describe_images_limited(
                image_paths=image_paths,
                labels=labels,
                max_concurrency=2
            )

            for idx, desc in enumerate(descriptions):
                if desc and desc.strip():
                    text_parts.append(
                        f"\n\n[DOCX - mô tả ảnh {idx + 1} bằng AI vision]\n{desc.strip()}"
                    )

        return "\n".join(text_parts).strip()
    
    def _extract_excel_text(
        self,
        file_path: str,
        file_name: str,
        max_rows_per_sheet: int = 500,
        max_cols_per_sheet: int = 50
    ) -> str:
        try:
            import pandas as pd
        except Exception:
            raise RuntimeError("Chưa cài pandas/openpyxl/xlrd để đọc Excel")

        text_parts = []

        try:
            sheets = pd.read_excel(
                file_path,
                sheet_name=None,
                dtype=str,
                engine=None
            )
        except Exception as e:
            raise ValueError(f"Không đọc được file Excel: {e}")

        for sheet_name, df in sheets.items():
            if df is None or df.empty:
                continue

            df = df.fillna("")

            original_rows = len(df)
            original_cols = len(df.columns)

            df = df.iloc[:max_rows_per_sheet, :max_cols_per_sheet]

            text_parts.append(
                f"\n\n[Excel: {file_name} | Sheet: {sheet_name}]\n"
                f"Số dòng gốc: {original_rows}, số cột gốc: {original_cols}. "
                f"Đang index tối đa {max_rows_per_sheet} dòng và {max_cols_per_sheet} cột đầu.\n"
            )

            columns = [str(c).strip() for c in df.columns]
            text_parts.append("Các cột: " + ", ".join(columns))

            for row_idx, row in df.iterrows():
                row_items = []

                for col in df.columns:
                    value = str(row[col]).strip()

                    if value:
                        row_items.append(f"{col}: {value}")

                if row_items:
                    text_parts.append(
                        f"Dòng {row_idx + 1}: " + " | ".join(row_items)
                    )

        result = "\n".join(text_parts).strip()

        if not result:
            raise ValueError("File Excel không có dữ liệu có thể đọc")

        return result
    
    def _extract_csv_text(
        self,
        file_bytes: bytes,
        file_name: str,
        max_rows: int = 1000,
        max_cols: int = 50
    ) -> str:
        try:
            import pandas as pd
            from io import BytesIO, StringIO
        except Exception:
            raise RuntimeError("Chưa cài pandas để đọc CSV")

        encodings = ["utf-8-sig", "utf-8", "latin1"]

        last_error = None
        df = None

        for enc in encodings:
            try:
                text = file_bytes.decode(enc, errors="ignore")
                df = pd.read_csv(StringIO(text), dtype=str)
                break
            except Exception as e:
                last_error = e

        if df is None:
            raise ValueError(f"Không đọc được file CSV: {last_error}")

        if df.empty:
            raise ValueError("File CSV không có dữ liệu")

        df = df.fillna("")

        original_rows = len(df)
        original_cols = len(df.columns)

        df = df.iloc[:max_rows, :max_cols]

        text_parts = [
            f"[CSV: {file_name}]",
            f"Số dòng gốc: {original_rows}, số cột gốc: {original_cols}. "
            f"Đang index tối đa {max_rows} dòng và {max_cols} cột đầu.",
            "Các cột: " + ", ".join([str(c).strip() for c in df.columns])
        ]

        for row_idx, row in df.iterrows():
            row_items = []

            for col in df.columns:
                value = str(row[col]).strip()

                if value:
                    row_items.append(f"{col}: {value}")

            if row_items:
                text_parts.append(
                    f"Dòng {row_idx + 1}: " + " | ".join(row_items)
                )

        return "\n".join(text_parts).strip()

    async def _describe_image_with_vision(self, image_path: str, page_label: str = "") -> str:
        prompt = f"""
Bạn là hệ thống đọc hiểu tài liệu bằng thị giác.

Nhiệm vụ:
- Quan sát ảnh/page tài liệu được cung cấp.
- Mô tả lại toàn bộ nội dung quan trọng có trong ảnh bằng tiếng Việt.
- Nếu có biểu đồ, bảng, sơ đồ, hãy mô tả ý nghĩa chính, các nhãn, số liệu nổi bật.
- Nếu có chữ trong ảnh, hãy trích lại các nội dung quan trọng.
- Không bịa thông tin không nhìn thấy.
- Trả lời dạng văn bản thuần, không JSON.

Ngữ cảnh ảnh: {page_label}
"""

        try:
            result = await _call_openrouter(
                prompt=prompt,
                model=VISION_MODEL,
                images=[image_path]
            )

            if not result or not str(result).strip():
                return ""

            return str(result).strip()

        except Exception as e:
            print(f"[DOC_RAG][VISION] Describe image error: {e}")
            return ""


    async def _describe_images_limited(self, image_paths: list, labels: list, max_concurrency: int = 2) -> list:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_one(path: str, label: str):
            async with semaphore:
                return await self._describe_image_with_vision(path, label)

        tasks = [
            run_one(path, labels[idx] if idx < len(labels) else f"Ảnh {idx + 1}")
            for idx, path in enumerate(image_paths)
        ]

        return await asyncio.gather(*tasks)

    async def prepare_document(self, file_id: str, message_id: str, room_id: str, user_email: str) -> dict:
        existing = await self.document_indexes_col.find_one({"file_id": file_id})

        if existing:
            existing.pop("_id", None)
            return {
                "status": existing.get("status"),
                "document_id": existing.get("document_id"),
                "chunk_count": existing.get("chunk_count", 0),
                "file_name": existing.get("file_name")
            }

        message_query = {
            "room_id": room_id,
            "content": file_id,
            "msg_type": "file"
        }

        if message_id:
            message_query["message_id"] = message_id

        message = await self.db.messages.find_one(message_query)

        if not message:
            raise ValueError("Không tìm thấy message tài liệu trong phòng chat")

        document_id = str(uuid.uuid4())

        await self.document_indexes_col.insert_one({
            "document_id": document_id,
            "file_id": file_id,
            "message_id": message.get("message_id"),
            "room_id": room_id,
            "channel_id": message.get("channel_id"),
            "file_name": message.get("file_name") or "document",
            "content_type": None,
            "status": "processing",
            "error": None,
            "chunk_count": 0,
            "created_at": dt.now(),
            "updated_at": dt.now()
        })

        try:
            await self.index_document(
                document_id=document_id,
                file_id=file_id,
                file_name=message.get("file_name") or "document"
            )

            doc = await self.document_indexes_col.find_one({"document_id": document_id})
            doc.pop("_id", None)

            return {
                "status": doc.get("status"),
                "document_id": document_id,
                "chunk_count": doc.get("chunk_count", 0),
                "file_name": doc.get("file_name")
            }

        except Exception as e:
            await self.document_indexes_col.update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "updated_at": dt.now()
                    }
                }
            )
            raise

    async def index_document(self, document_id: str, file_id: str, file_name: str):
        file_bytes = await self._download_file_bytes(file_id)
        text = await self._extract_text(file_bytes, file_name)

        if not text.strip():
            raise ValueError("Không đọc được nội dung tài liệu")

        chunks = self._split_text(text)

        model = self._get_embedding_model()

        embeddings = model.encode(
            [f"passage: {chunk}" for chunk in chunks],
            normalize_embeddings=True
        )

        await self.document_chunks_col.delete_many({"document_id": document_id})

        chunk_docs = []

        for idx, chunk in enumerate(chunks):
            chunk_docs.append({
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "file_id": file_id,
                "chunk_index": idx,
                "text": chunk,
                "embedding": embeddings[idx].astype(float).tolist(),
                "metadata": {
                    "file_name": file_name
                },
                "created_at": dt.now()
            })

        if chunk_docs:
            await self.document_chunks_col.insert_many(chunk_docs)

        await self.document_indexes_col.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": "ready",
                    "chunk_count": len(chunk_docs),
                    "updated_at": dt.now()
                }
            }
        )

    async def _download_file_bytes(self, file_id: str) -> bytes:
        url = FileService.get_file_url(file_id)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def _decode_text_file(self, file_bytes: bytes, file_name: str) -> str:
        encodings = [
            "utf-8-sig",
            "utf-8",
            "cp1258",
            "cp1252",
            "latin1",
        ]

        last_error = None

        for enc in encodings:
            try:
                text = file_bytes.decode(enc)

                if text and text.strip():
                    return f"[File text/code: {file_name}]\n{text.strip()}"

            except Exception as e:
                last_error = e

        text = file_bytes.decode("utf-8", errors="ignore")

        if text and text.strip():
            return f"[File text/code: {file_name}]\n{text.strip()}"

        raise ValueError(f"Không đọc được nội dung file text/code: {file_name}. Lỗi: {last_error}")

    async def _extract_text(self, file_bytes: bytes, file_name: str) -> str:
        ext = os.path.splitext(file_name)[1].lower()

        code_text_extensions = [
            ".txt", ".md",

            # JavaScript / TypeScript
            ".js", ".jsx", ".ts", ".tsx",

            # Python / Java / C-family
            ".py", ".java",
            ".c", ".cpp", ".h", ".hpp",
            ".cs",

            # Web / backend
            ".php", ".rb", ".go", ".rs",
            ".html", ".css",

            # Data / config / query
            ".json", ".xml", ".yml", ".yaml",
            ".sql",

            # Script
            ".sh", ".bat", ".cmd",
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, f"document{ext}")

            with open(tmp_path, "wb") as f:
                f.write(file_bytes)

            if ext == ".pdf":
                return await self._extract_pdf_text_with_vision(
                    pdf_path=tmp_path,
                    file_name=file_name,
                    tmp_dir=tmp_dir
                )

            if ext == ".docx":
                return await self._extract_docx_text_with_images(
                    docx_path=tmp_path,
                    file_name=file_name,
                    tmp_dir=tmp_dir
                )

            if ext in [".xlsx", ".xls"]:
                return self._extract_excel_text(
                    file_path=tmp_path,
                    file_name=file_name
                )

            if ext == ".csv":
                return self._extract_csv_text(
                    file_bytes=file_bytes,
                    file_name=file_name
                )

            if ext in code_text_extensions:
                return self._decode_text_file(file_bytes=file_bytes, file_name=file_name)

            raise ValueError(f"Định dạng chưa hỗ trợ: {ext}")

    def _split_text(self, text: str, chunk_size: int = 1400, overlap: int = 250) -> List[str]:
        text = " ".join(text.split())
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def get_document_by_file_id(self, file_id: str) -> Optional[dict]:
        doc = await self.document_indexes_col.find_one({"file_id": file_id})
        if doc:
            doc.pop("_id", None)
        return doc

    async def get_history(self, file_id: str, user_email: str) -> List[dict]:
        doc = await self.get_document_by_file_id(file_id)

        if not doc:
            return []

        conversation_id = self._conversation_id(user_email, doc["document_id"])

        cursor = self.document_ai_messages_col.find(
            {"conversation_id": conversation_id}
        ).sort("created_at", 1)

        messages = []

        async for item in cursor:
            item.pop("_id", None)
            messages.append(item)

        return messages

    async def ask_document(self, file_id: str, user_email: str, question: str) -> dict:
        doc = await self.get_document_by_file_id(file_id)

        if not doc:
            raise ValueError("Tài liệu chưa được index")

        if doc.get("status") != "ready":
            raise ValueError("Tài liệu chưa sẵn sàng để hỏi AI")

        document_id = doc["document_id"]
        conversation_id = self._conversation_id(user_email, document_id)

        history = await self.get_history(file_id, user_email)
        chunks = await self._retrieve_chunks(document_id, question, top_k=5)

        context = "\n\n".join(
            f"[Đoạn {idx + 1}]\n{chunk['text']}"
            for idx, chunk in enumerate(chunks)
        )

        recent_history = history[-8:]

        history_text = "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
            for h in recent_history
        )

        prompt = f"""
Bạn là UTEZoneAI, trợ lý hỏi đáp tài liệu trong hệ thống UTEZone.

Quy tắc:
- Chỉ trả lời dựa trên tài liệu và lịch sử hội thoại.
- Nếu tài liệu không có thông tin, nói rõ: "Mình không tìm thấy thông tin này trong tài liệu."
- Hiểu câu hỏi tiếp theo dựa trên lịch sử hội thoại.
- Nếu tài liệu là Excel/CSV, hãy hiểu nội dung theo dạng bảng: sheet, cột, dòng, số liệu, xu hướng và quan hệ giữa các cột.
- Khi trả lời về số liệu, hãy nói rõ đang dựa trên sheet/cột nào nếu có thể.
- Trả lời bằng tiếng Việt.
- Format câu trả lời đẹp, dễ đọc bằng Markdown cơ bản.
- Dùng tiêu đề ngắn nếu cần.
- Dùng bullet list khi liệt kê ý.
- Dùng **in đậm** cho ý quan trọng.
- Không dùng bảng nếu không thật sự cần.
- Không dùng markdown code block trừ khi người dùng hỏi về code.

Tên tài liệu: {doc.get("file_name")}

Lịch sử hội thoại gần đây:
{history_text}

Các đoạn tài liệu liên quan:
{context}

Lưu ý:
Một số đoạn có nhãn "mô tả hình ảnh/page bằng AI vision". Đây là phần UTEZoneAI đã quan sát ảnh hoặc page tài liệu và mô tả lại.
Nếu câu hỏi liên quan biểu đồ, ảnh, sơ đồ hoặc nội dung scan, hãy ưu tiên các đoạn mô tả vision đó.

Câu hỏi hiện tại:
{question}
"""

        answer = await _call_openrouter(prompt, TEXT_MODEL)

        await self.document_ai_messages_col.insert_many([
            {
                "message_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "document_id": document_id,
                "file_id": file_id,
                "user_email": user_email,
                "role": "user",
                "content": question,
                "created_at": dt.now()
            },
            {
                "message_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "document_id": document_id,
                "file_id": file_id,
                "user_email": user_email,
                "role": "assistant",
                "content": answer,
                "created_at": dt.now()
            }
        ])

        return {
            "answer": answer,
            "document_id": document_id,
            "file_id": file_id
        }

    async def _retrieve_chunks(self, document_id: str, query: str, top_k: int = 5) -> List[dict]:
        model = self._get_embedding_model()

        query_embedding = model.encode(
            [f"query: {query}"],
            normalize_embeddings=True
        )[0]

        cursor = self.document_chunks_col.find({"document_id": document_id})
        scored = []

        async for chunk in cursor:
            emb = np.array(chunk["embedding"], dtype=np.float32)
            score = float(np.dot(query_embedding, emb))

            chunk.pop("_id", None)
            chunk["score"] = score

            scored.append(chunk)

        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored[:top_k]


document_rag_service = DocumentRAGService()