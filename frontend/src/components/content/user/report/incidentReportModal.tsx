// IncidentReportModal.tsx

import { useState } from "react";
import "./incidentReportModal.css";
import { reportAPI } from "../../../../services/ReportService";
import { ToastService } from "../../../../services/ToastService";

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export default function IncidentReportModal({
  isOpen,
  onClose,
}: Props) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!content.trim()) {
      ToastService.error("Vui lòng nhập sự cố bạn gặp phải");;
      return;
    }

    try {
      setLoading(true);

      await reportAPI.addIncidentReport({
        content,
      });

      ToastService.success("Báo cáo đã được gửi thành công. Chúng tôi sẽ xem xét và phản hồi sớm nhất có thể.");

      setContent("");
      onClose();
    } catch (error) {
      console.error(error);
      ToastService.error("Gửi báo cáo thất bại");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="incidentModalOverlay"
      onClick={onClose}
    >
      <div
        className="incidentModalContainer"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="incidentModalHeader">
          <h2>🚨 Báo cáo sự cố</h2>

          <button
            className="incidentCloseBtn"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="incidentModalBody">
          <p className="incidentHint">
            Hãy mô tả chi tiết sự cố bạn gặp phải để
            quản trị viên có thể hỗ trợ nhanh hơn.
          </p>

          <textarea
            className="incidentTextarea"
            placeholder="Ví dụ: Tôi không thể gửi tin nhắn, hệ thống bị lỗi khi đăng bài..."
            value={content}
            onChange={(e) =>
              setContent(e.target.value)
            }
          />

          <div className="incidentActions">
            <button
              className="incidentCancelBtn"
              onClick={onClose}
            >
              Hủy
            </button>

            <button
              className="incidentSubmitBtn"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading
                ? "Đang gửi..."
                : "Gửi báo cáo"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}