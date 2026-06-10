// ForumPolicyModal.tsx

import { useEffect, useState } from "react";
import "./policyModal.css";
import { reportAPI } from "../../../../services/ReportService";

interface PolicyItem {
  _id: string;
  name: string;
  description: string;
  level: number;
  status: string;
  createdAt: string;
  updatedAt: string;
  action: {
    permission: string;
    detail: string;
  } | null;
}

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export default function PolicyModal({ isOpen, onClose }: Props) {
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const fetchPolicies = async () => {
      try {
        setLoading(true);

        const res = await reportAPI.getAllPolicy();
        setPolicies(res.policy_list || []);
      } catch (error) {
        console.error("Lỗi lấy chính sách:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchPolicies();
  }, [isOpen]);

  if (!isOpen) return null;

  const formatDate = (date: string) => {
    return new Date(date).toLocaleString("vi-VN");
  };

  return (
    <div className="policyModalOverlay" onClick={onClose}>
      <div
        className="policyModalContainer"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="policyModalHeader">
          <h2>📜 Chính sách diễn đàn</h2>

          <button className="policyCloseBtn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="policyModalBody">
          {loading ? (
            <div className="policyLoading">Đang tải chính sách...</div>
          ) : policies.length === 0 ? (
            <div className="policyEmpty">Không có chính sách nào</div>
          ) : (
            policies.map((policy) => (
              <div key={policy._id} className="policyCard">
                <div className="policyTop">
                  <div>
                    <h3>{policy.name}</h3>

                    <div className="policyMeta">
                      <span> Mức độ: {policy.level}</span>

                      <span> Cập nhật: {formatDate(policy.updatedAt)}</span>
                    </div>
                  </div>

                  <div className={`policyStatus ${policy.status}`}>
                    {policy.status === "active"
                      ? "Đang áp dụng"
                      : "Ngừng áp dụng"}
                  </div>
                </div>

                <p className="policyDescription">{policy.description}</p>

                {policy.action && (
                  <div className="policyAction">
                    <strong>Hình phạt:</strong> {policy.action.detail}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
