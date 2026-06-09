// CreatePostCatalogModal.tsx

import { useEffect, useState } from "react";
import "./createPostCatalog.css";
import { X, CalendarDays, Sparkles, Trash2 } from "lucide-react";

import { catalogService } from "../../../../services/CatalogService";
import { ToastService } from "../../../../services/ToastService";

interface Props {
  open: boolean;
  onClose: () => void;
  postId: string;
  isCreateCatalog: boolean;
  onSuccess?: () => void;
}

export default function CreatePostCatalogModal({
  open,
  onClose,
  postId,
  isCreateCatalog,
  onSuccess,
}: Props) {
  const [title, setTitle] = useState("");
  const [endAt, setEndAt] = useState("");

  const [loading, setLoading] = useState(false);

  const [catalogId, setCatalogId] = useState("");

  // =========================
  // LOAD DATA WHEN UPDATE
  // =========================
  useEffect(() => {
  if (!open) return;

  if (isCreateCatalog) {
    fetchCatalogDetail();
  }
}, [open, isCreateCatalog]);

  const fetchCatalogDetail = async () => {
    try {
      const res = await catalogService.findPostCatalog(postId);

      const catalog = res?.post_catalog;

      if (!catalog) return;

      setCatalogId(catalog._id);

      setTitle(catalog.name || "");

      // convert datetime
      const formattedDate = catalog.end_at?.slice(0, 16);

      setEndAt(formattedDate);
    } catch (error) {
      ToastService.error("Không lấy được thông tin sự kiện");
    }
  };

  // =========================
  // CREATE
  // =========================
  const handleCreate = async () => {
    try {
      if (!title.trim()) {
        alert("Vui lòng nhập title");
        return;
      }

      if (!endAt) {
        ToastService.error("Vui lòng chọn thời gian kết thúc");
        return;
      }

      setLoading(true);

      await catalogService.addPostCatalog({
        name: title,
        post_id: postId,
        end_at: endAt,
      });

      ToastService.success("Tạo sự kiện thành công");

      onSuccess?.();
      onClose();
    } catch (error) {
      console.error(error);
      ToastService.error("Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // UPDATE
  // =========================
  const handleUpdate = async () => {
    try {
      if (!title.trim()) {
        ToastService.error("Vui lòng nhập title");
        return;
      }

      if (!endAt) {
        ToastService.error("Vui lòng chọn thời gian kết thúc");
        return;
      }

      setLoading(true);

      await catalogService.updatePostCatalog(postId, {
        name: title,
        end_at: endAt,
      });

      ToastService.success("Cập nhật thành công");

      onSuccess?.();
      onClose();
    } catch (error) {
      console.error(error);
      ToastService.error("Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // DELETE
  // =========================
  const handleDelete = async () => {
    try {
      const confirmDelete = window.confirm("Bạn có chắc muốn xóa sự kiện?");

      if (!confirmDelete) return;

      setLoading(true);

      await catalogService.deletePostCatalog(postId);

      ToastService.success("Xóa sự kiện thành công");

      resetForm();

      onSuccess?.();
      onClose();
    } catch (error) {
      console.error(error);
      ToastService.error("Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setTitle("");
    setEndAt("");
    setCatalogId("");
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  if (!open) return null;

  return (
    <div className="catalog-modal-overlay">
      <div className="catalog-modal">
        {/* HEADER */}
        <div className="catalog-modal-header">
          <div className="catalog-header-left">
            <div className="catalog-icon">
              <Sparkles size={20} />
            </div>

            <div>
              <h2>{isCreateCatalog ? "Cập nhật sự kiện" : "Tạo sự kiện"}</h2>

              <p>Hiển thị bài viết tại slider nổi bật</p>
            </div>
          </div>

          <button className="catalog-close-btn" onClick={handleClose}>
            <X size={20} />
          </button>
        </div>

        {/* BODY */}
        <div className="catalog-modal-body">
          {/* TITLE */}
          <div className="catalog-input-group">
            <label>Tiêu đề sự kiện</label>

            <input
              type="text"
              placeholder="VD: Workshop AI cho sinh viên"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* END DATE */}
          <div className="catalog-input-group">
            <label>
              <CalendarDays size={16} />
              Thời gian kết thúc
            </label>

            <input
              type="datetime-local"
              value={endAt}
              onChange={(e) => setEndAt(e.target.value)}
            />
          </div>
        </div>

        {/* FOOTER */}
        <div className="catalog-modal-footer">
          {/* DELETE BUTTON */}
          <button
  className="catalog-delete-btn"
  onClick={handleDelete}
  disabled={loading}
  style={{
    visibility: isCreateCatalog
      ? "visible"
      : "hidden",
  }}
>
  <Trash2 size={16} />
  Xóa sự kiện
</button>

          <div className="catalog-footer-right">
            <button className="catalog-cancel-btn" onClick={handleClose}>
              Hủy
            </button>

            <button
              className="catalog-submit-btn"
              onClick={isCreateCatalog ? handleUpdate : handleCreate}
              disabled={loading}
            >
              {loading
                ? isCreateCatalog
                  ? "Đang cập nhật..."
                  : "Đang tạo..."
                : isCreateCatalog
                  ? "Cập nhật"
                  : "Tạo sự kiện"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
