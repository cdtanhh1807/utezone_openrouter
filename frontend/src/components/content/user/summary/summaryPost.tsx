import Draggable from "react-draggable";
import { useRef } from "react";
import { Sparkles, GripHorizontal } from "lucide-react";
import CloseIcon from "@mui/icons-material/Close";
import "./summaryPost.css";
import logoAI from "../../../../assets/logoAI.png";

interface SummaryBoxProps {
  summary: string;
  postId?: string;
  onClose: () => void;
  onViewDetail?: () => void;
}

export default function SummaryBox({
  summary,
  postId,
  onClose,
  onViewDetail,
}: SummaryBoxProps) {
  const nodeRef = useRef<HTMLDivElement>(null);

  return (
    <Draggable nodeRef={nodeRef} handle=".summary-header">
      <div ref={nodeRef} className="summary-box">
        {/* Header */}
        <div className="summary-header">
          <div className="summary-ai-info">
            <div className="summary-avatar-wrapper">
              <img src={logoAI} className="summary-avatar" alt="AI Avatar" />
            </div>

            <div className="summary-ai-text">
              <div className="summary-ai-title-row">
                <span className="summary-ai-name">UTE AI</span>
                <GripHorizontal size={14} className="summary-header-grip" />
              </div>
              <span className="summary-ai-status">
                <Sparkles size={12} />
                Trợ lý ảo thông minh
              </span>
            </div>
          </div>

          <div className="summary-actions">
            <button
              className="summary-action-btn close"
              onClick={onClose}
              title="Đóng"
            >
              <CloseIcon sx={{ fontSize: 16 }} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="summary-content">
          <div className="summary-badge">
            <Sparkles size={13} />
            Tóm tắt bài viết
          </div>

          <p className="summary-text-p">{summary}</p>

          {postId && onViewDetail && (
            <button className="summary-detail-btn" onClick={onViewDetail}>
              Xem chi tiết bài viết →
            </button>
          )}
        </div>
      </div>
    </Draggable>
  );
}