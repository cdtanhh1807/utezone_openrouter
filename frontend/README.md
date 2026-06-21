# UTE Zone - Frontend Web Application

Tài liệu chi tiết về cấu trúc thư mục, kiến trúc hệ thống và hướng dẫn phát triển cho phần **Frontend (Vite + React)** của dự án **UTE Zone** (Mạng xã hội/Diễn đàn nội bộ dành cho sinh viên và cán bộ giảng viên trường Đại học Sư phạm Kỹ thuật TP.HCM).

---

## 🚀 Công Nghệ Sử Dụng (Tech Stack)

Ứng dụng Frontend được xây dựng trên các công nghệ hiện đại, đảm bảo hiệu năng tối ưu, trải nghiệm người dùng mượt mà và khả năng bảo trì cao:

*   **Core Framework:** [React 19](https://react.dev/) & [TypeScript](https://www.typescriptlang.org/)
*   **Build Tool:** [Vite 7](https://vite.dev/) (Cung cấp tốc độ Hot Module Replacement cực nhanh)
*   **Styling & UI Components:** 
    *   [Material-UI (MUI v7)](https://mui.com/) cho các component hệ thống (nút, icon, modal, loading, v.v.).
    *   [Emotion CSS](https://emotion.sh/) & Vanilla CSS Modules cho các kiểu thiết kế tùy biến sâu.
*   **Routing:** [React Router DOM (v7)](https://reactrouter.com/) (Hỗ trợ định tuyến phân tầng và route guards).
*   **State Management:** [Zustand](https://zustand-demo.pmnd.rs/) (Quản lý trạng thái nhẹ, không cần boilerplate phức tạp như Redux).
*   **API Client:** [Axios](https://axios-http.com/) (Tích hợp interceptors để đính kèm Token và xử lý mã lỗi 401 tự động).
*   **Realtime Communication:** WebSockets (Quản lý luồng trò chuyện trực tiếp).
*   **Hiệu Ứng & Hoạt Họa:** [Framer Motion](https://www.framer.com/motion/) cho các hiệu ứng chuyển trang và mở hộp thoại mượt mà.
*   **Hiển Thị Biểu Đồ:** [Apexcharts](https://apexcharts.com/) / [React Apexcharts](https://github.com/apexcharts/react-apexcharts) & [Recharts](https://recharts.org/) cho phần Admin Dashboard.
*   **Xử Lý Đa Phương Tiện:** [Wavesurfer.js](https://wavesurfer-js.org/) để phát các tệp âm thanh (ghi âm chat).
*   **Các thư viện bổ trợ khác:** `react-toastify` (thông báo popup), `emoji-picker-react` (chọn biểu tượng cảm xúc), `react-datepicker` (chọn ngày), `react-draggable` (kéo thả giao diện chat).

---

## 📁 Cấu Trúc Thư Mục Dự Án

Thư mục nguồn chính nằm trong `/src` được phân chia một cách khoa học theo cấu trúc Module/Component:

```text
src/
├── assets/                    # Hình ảnh, logo, tệp tĩnh dùng chung
├── components/
│   └── content/
│       ├── admin/             # Các component dành riêng cho Quản trị viên (Admin)
│       │   ├── AccountManager.tsx       # Quản lý tài khoản người dùng
│       │   ├── AdminDashboard.tsx       # Layout chính & Sidebar của Admin
│       │   ├── ApproveHistory.tsx       # Lịch sử phê duyệt và kiểm duyệt bài viết
│       │   ├── BanManager.tsx           # Quản lý lệnh cấm/chặn tài khoản
│       │   ├── ComplaintManager.tsx     # Quản lý đơn khiếu nại của thành viên
│       │   ├── Dashboard.tsx            # Báo cáo số liệu, biểu đồ thống kê
│       │   ├── IncidentReportManager.tsx# Quản lý báo cáo lỗi từ hệ thống
│       │   ├── PolicyManager.tsx        # Chỉnh sửa chính sách, quy chế của diễn đàn
│       │   └── ReportManager.tsx        # Tiếp nhận & xử lý tố cáo vi phạm bài viết/bình luận
│       │
│       ├── auth/              # Luồng đăng nhập, đăng ký, khôi phục tài khoản
│       │   ├── forgotpassword/          # Quên mật khẩu & xác thực OTP
│       │   ├── google/                  # Đăng nhập nhanh qua Google OAuth
│       │   ├── login/                   # Giao diện Đăng nhập chính
│       │   ├── signup/                  # Giao diện Đăng ký tài khoản mới
│       │   └── verifyotp/               # Xác minh mã OTP sau khi đăng ký
│       │
│       └── user/              # Các tính năng chính dành cho Sinh viên / Giảng viên / Moderator
│           ├── appeal/                  # Gửi đơn khiếu nại khi bị khóa bài/tài khoản
│           ├── chat/                    # Module nhắn tin thời gian thực (WebSockets)
│           ├── common/                  # Component dùng chung (ToastProvider, v.v.)
│           ├── create/                  # Chức năng tạo bài viết, tạo tin (Story), chia sẻ bài viết
│           ├── home/                    # Bảng tin (Home Feed), layout và slider sự kiện
│           ├── notification/            # Hệ thống nhận thông báo trong ứng dụng
│           ├── post/                    # Chi tiết bài viết, lượt tương tác, bình luận đa cấp
│           ├── profile/                 # Trang cá nhân, bộ sưu tập lưu trữ, hoàn thành hồ sơ
│           ├── relationship/            # Danh sách người theo dõi, đang theo dõi, danh sách khoa
│           ├── report/                  # Modals tố cáo, xem chính sách và báo cáo sự cố
│           ├── stores/                  # Zustand stores quản lý trạng thái cục bộ của user
│           │   ├── aiModerationStore.ts   # Quản lý trạng thái AI kiểm duyệt nội dung tự động
│           │   └── aiStore.ts             # Trạng thái hiển thị tóm tắt nội dung bằng AI
│           └── summary/                 # Tích hợp AI (Nút AI, khung hiển thị tóm tắt bài viết)
│
├── services/                  # Các lớp dịch vụ giao tiếp với Backend API (Axios)
│   ├── AIService.ts           # Dịch vụ tóm tắt/kiểm duyệt thông qua AI
│   ├── AccountService.ts      # API quản lý tài khoản, thông tin người dùng, mối quan hệ
│   ├── AnnounceService.ts     # API lấy thông báo chung toàn trường
│   ├── CommentService.ts      # API tương tác với bình luận (thêm, sửa, xóa, tương tác)
│   ├── PostService.ts         # API CRUD bài viết, danh mục, ghim bài
│   └── ...                    # Các API service khác (Story, Saved, Report, File)
│
├── styles/                    # Các tệp CSS dùng chung
├── types/                     # Định nghĩa TypeScript interface (Account, Post, Comment, Story, v.v.)
├── utils/                     # Tiện ích bổ trợ (Auth check, AxiosInstance cấu hình chung)
│   ├── Auth.ts                # Kiểm tra hạn sử dụng JWT Token
│   └── AxiosInstance.ts       # Cấu hình Axios Interceptors (Token header, Auto logout 401)
│
├── App.tsx                    # Điểm định tuyến chính, quản lý Guards và polling thông báo chung
├── index.css                  # CSS cấu hình cơ bản toàn hệ thống
└── main.tsx                   # Điểm khởi chạy của ứng dụng React (Root)
```

---

## 🏛️ Kiến Trúc Hệ Thống & Luồng Dữ Liệu

### 1. Quản lý Định Tuyến và Phân Quyền (Routing & Guards)
Được cấu hình tập trung trong `src/App.tsx`, chia làm 3 nhóm quyền chính sử dụng cơ chế bảo vệ Route (Route Guards) dựa trên giải mã JWT Token:
*   **RootRedirect (`/`):** Tự động phân tích Token hiện tại để điều hướng người dùng đến `/welcome` (nếu chưa đăng nhập), `/admin` (nếu là Administrator) hoặc `/home` (nếu là Sinh viên/Giảng viên/Moderator).
*   **GuestGuard:** Chỉ cho phép truy cập khi chưa đăng nhập. Bảo vệ các trang: `/welcome`, `/login`, `/signup`, `/verify-otp`, `/forgot-password`.
*   **UserOnlyGuard:** Chỉ cho phép người dùng thông thường và Moderator truy cập. Bảo vệ các trang: `/home`, `/profile`, `/profile/:email`, `/search`, `/complete-profile`.
*   **AdminOnlyGuard:** Bảo vệ nghiêm ngặt các trang quản trị `/admin/*`, chỉ tài khoản có vai trò `Administrator` mới được phép truy cập.

### 2. Giao Tiếp API (Axios Interceptors)
Tất cả các API gửi đến máy chủ Backend (`http://localhost:8000`) đều đi qua [AxiosInstance](file:///c:/Users/ToanMihn/Documents/BackendKLTN-10-6-2026/utezone_openrouter/frontend/src/utils/AxiosInstance.ts):
*   **Request Interceptor:** Kiểm tra `localStorage` để lấy `token`. Nếu tồn tại, tự động đính kèm vào HTTP Header dưới dạng `Authorization: Bearer <token>`.
*   **Response Interceptor:** Lắng nghe phản hồi từ Backend. Nếu phản hồi trả về lỗi `401 Unauthorized` (Token hết hạn hoặc không hợp lệ), ứng dụng sẽ tự động xóa `token` khỏi `localStorage` để bảo mật và buộc người dùng đăng nhập lại.

### 3. Đồng bộ Trạng thái Thời gian thực (Real-time WebSockets)
Hệ thống chat của **UTE Zone** (`src/components/content/user/chat`) sử dụng kết nối WebSocket để trao đổi tin nhắn tức thời:
*   `useWebSocket.ts` quản lý việc khởi tạo và đóng kết nối socket dựa trên Token hiện tại của người dùng.
*   `useConversation.ts` và `useChat.ts` xử lý dữ liệu danh sách hội thoại, cập nhật tin nhắn mới, hiển thị trạng thái đang nhập chữ (typing) và quản lý tải lên các phương tiện truyền thông (hình ảnh, tệp đính kèm).

### 4. Tích Hợp Trí Tuệ Nhân Tạo (UTEZone AI Integration)
Hệ thống sử dụng AI để nâng cao trải nghiệm và an toàn thông tin:
*   **Tóm Tắt Bài Viết:** Người dùng có thể nhấn nút UTEZone AI để tự động tóm tắt nhanh các bài viết dài thông qua `AIService.ts`. Trạng thái tóm tắt được lưu trữ trong `aiStore.ts` để hiển thị khung thông tin thông qua **React Portal** (`aiSummaryPortal.tsx`) đè lên trên giao diện chính mà không làm vỡ bố cục DOM.
*   **Kiểm Duyệt Tự Động:** Khi đăng tải nội dung, hệ thống sẽ kích hoạt trạng thái kiểm duyệt nội dung trong `aiModerationStore.ts` để quét và chặn các ngôn từ thù ghét hoặc hình ảnh nhạy cảm trước khi hiển thị lên Bảng tin.

---

## 🛠️ Hướng Dẫn Cài Đặt & Chạy Dự Án

Hãy chắc chắn rằng máy tính của bạn đã được cài đặt [Node.js](https://nodejs.org/) (Khuyến nghị phiên bản 18+).

### 1. Cài đặt các thư viện phụ thuộc
Mở terminal tại thư mục root của frontend và chạy lệnh:
```bash
npm install
```

### 2. Chạy môi trường phát triển (Development)
Khởi chạy máy chủ phát triển cục bộ với tính năng Hot Reload:
```bash
npm run dev
```
Sau khi khởi chạy thành công, ứng dụng sẽ chạy tại địa chỉ mặc định: `http://localhost:5173`.

### 3. Kiểm tra lỗi mã nguồn (Linting)
Chạy ESLint để phân tích và cảnh báo lỗi cú pháp hoặc vi phạm quy tắc viết code:
```bash
npm run lint
```

### 4. Biên dịch dự án (Build Production)
Biên dịch dự án thành mã nguồn HTML/JS/CSS tối ưu để đưa lên máy chủ sản xuất:
```bash
npm run build
```
Bản dựng hoàn chỉnh sẽ được xuất ra thư mục `/dist`.

---

*Tài liệu này được biên soạn nhằm phục vụ công tác phát triển, mở rộng và bảo trì dự án UTE Zone Frontend. Mọi thay đổi liên quan đến cấu trúc thư mục hoặc công nghệ cốt lõi cần được thảo luận và thống nhất trước khi thực hiện.*
