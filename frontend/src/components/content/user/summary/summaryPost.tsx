import Draggable from "react-draggable";
import { useRef } from "react";
import {
  Sparkles,
  X,
  Minimize2,
  GripHorizontal,
} from "lucide-react";
import "./summaryPost.css";
import logoAI from "../../../../assets/logoAI.png";

interface SummaryBoxProps {
  summary: string;
  onClose: () => void;
}

export default function SummaryBox({
  summary,
  onClose,
}: SummaryBoxProps) {
  const nodeRef = useRef<HTMLDivElement>(null);

  return (
    <Draggable nodeRef={nodeRef} handle=".summary-header">
      <div ref={nodeRef} className="summary-box">
        {/* Header */}
        <div className="summary-header">
          <div className="summary-ai-info">
            <div className="summary-avatar-wrapper">
              <img src={logoAI} className="summary-avatar" />
            </div>

            <div className="summary-ai-text">
              <span className="summary-ai-name">UTE AI</span>
              <span className="summary-ai-status">
                <Sparkles size={13} />
                Trợ lý ảo thông minh
              </span>
            </div>
          </div>

          <div className="summary-actions">
            {/* <button className="summary-action-btn">
              <Minimize2 size={16} />
            </button> */}

            <button
              className="summary-action-btn close"
              onClick={onClose}
            >
              x
            </button>
          </div>
        </div>

        {/* Drag Hint */}
        <div className="summary-drag">
          <GripHorizontal size={18} />
        </div>

        {/* Content */}
        <div className="summary-content">
          <div className="summary-badge">
            <Sparkles size={14} />
            Nội dung tóm tắt
          </div>

          <p>{summary}</p>
        </div>
      </div>
    </Draggable>
  );
}