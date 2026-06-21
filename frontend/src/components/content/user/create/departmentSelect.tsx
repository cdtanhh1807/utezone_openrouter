import { useState, useRef, useEffect } from "react";
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import "./departmentSelect.css";

const departments = [
  "TẤT CẢ",
  "CHÍNH TRỊ VÀ LUẬT",
  "CƠ KHÍ CHẾ TẠO MÁY",
  "CÔNG NGHỆ HÓA HỌC VÀ THỰC PHẨM",
  "CÔNG NGHỆ THÔNG TIN",
  "ĐÀO TẠO TIÊN TIẾN",
  "ĐIỆN - ĐIỆN TỬ",
  "GIAO THÔNG VÀ NĂNG LƯỢNG",
  "IN VÀ TRUYỀN THÔNG",
  "KHOA HỌC ỨNG DỤNG",
  "KINH TẾ",
  "NGOẠI NGỮ",
  "THỜI TRANG VÀ DU LỊCH",
  "XÂY DỰNG",
  "VIỆN SƯ PHẠM KỸ THUẬT",
];

const displayNames: Record<string, string> = {
  "TẤT CẢ": "Tất cả phòng/khoa",
  "CHÍNH TRỊ VÀ LUẬT": "Chính trị và Luật",
  "CƠ KHÍ CHẾ TẠO MÁY": "Cơ khí Chế tạo máy",
  "CÔNG NGHỆ HÓA HỌC VÀ THỰC PHẨM": "Công nghệ Hóa học và Thực phẩm",
  "CÔNG NGHỆ THÔNG TIN": "Công nghệ Thông tin",
  "ĐÀO TẠO TIÊN TIẾN": "Đào tạo Tiên tiến",
  "ĐIỆN - ĐIỆN TỬ": "Điện - Điện tử",
  "GIAO THÔNG VÀ NĂNG LƯỢNG": "Giao thông và Năng lượng",
  "IN VÀ TRUYỀN THÔNG": "In và Truyền thông",
  "KHOA HỌC ỨNG DỤNG": "Khoa học Ứng dụng",
  "KINH TẾ": "Kinh tế",
  "NGOẠI NGỮ": "Ngoại ngữ",
  "THỜI TRANG VÀ DU LỊCH": "Thời trang và Du lịch",
  "XÂY DỰNG": "Xây dựng",
  "VIỆN SƯ PHẠM KỸ THUẬT": "Viện Sư phạm Kỹ thuật",
};
export default function DepartmentMultiSelect({ selectedDepartments, setSelectedDepartments }: { selectedDepartments: string[], setSelectedDepartments: (vals: string[]) => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleSelection = (dept: string) => {
    if (dept === "TẤT CẢ") {
      if (selectedDepartments.includes("TẤT CẢ")) {
        setSelectedDepartments([]);
      } else {
        setSelectedDepartments([...departments]); // chọn tất cả các mục
      }
      return;
    }
    
    let newSelection: string[] = [];
    if (selectedDepartments.includes(dept)) {
      newSelection = selectedDepartments.filter(d => d !== dept && d !== "TẤT CẢ");
    } else {
      newSelection = [...selectedDepartments.filter(d => d !== "TẤT CẢ"), dept];
    }
    
    const allSelected = departments.slice(1).every(d => newSelection.includes(d));
    if (allSelected) {
      newSelection = ["TẤT CẢ", ...departments.slice(1)];
    }

    setSelectedDepartments(newSelection);
  };

  const getTriggerText = () => {
    const isAll = selectedDepartments.includes("TẤT CẢ") || 
      (selectedDepartments.length > 0 && departments.slice(1).every(d => selectedDepartments.includes(d)));
      
    if (isAll) {
      return displayNames["TẤT CẢ"];
    }
    if (selectedDepartments.length === 0) {
      return "Chọn phòng/khoa";
    }
    if (selectedDepartments.length === 1) {
      return displayNames[selectedDepartments[0]] || selectedDepartments[0];
    }
    // Lọc bỏ "TẤT CẢ" để đếm chính xác số lượng phòng/khoa thực tế được chọn
    const count = selectedDepartments.filter(d => d !== "TẤT CẢ").length;
    return `Đã chọn ${count} phòng/khoa`;
  };

  return (
    <div className="departmentSelector" ref={menuRef}>
      <div className="dept-select-trigger" onClick={() => setMenuOpen(prev => !prev)}>
        <span className="dept-select-text">
          {getTriggerText()}
        </span>
        <KeyboardArrowDownIcon className={`dept-select-arrow ${menuOpen ? "open" : ""}`} />
      </div>

      {menuOpen && (
        <div className="departmentMenu">
          {departments.map((dept) => {
            const isSelected = selectedDepartments.includes(dept);
            return (
              <div
                key={dept}
                className={`departmentItem ${isSelected ? "active" : ""}`}
                onClick={() => toggleSelection(dept)}
              >
                <div className={`dept-checkbox ${isSelected ? "checked" : ""}`}>
                  {isSelected && (
                    <svg viewBox="0 0 24 24" className="checkmark">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </div>
                <span className="dept-name">{displayNames[dept] || dept}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
