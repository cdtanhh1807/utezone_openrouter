import { GoogleLogin } from "@react-oauth/google";
import { jwtDecode } from "jwt-decode";
import axiosInstance from "../../../../utils/AxiosInstance";
import AccountService from "../../../../services/AccountService";
import { useNavigate } from "react-router-dom";
import { ToastService } from "../../../../services/ToastService";
import "./GoogleLoginBtn.css";

interface BackendJwtPayload {
  sub: string;
  role: string;
  per: string;
  exp: number;
}

interface GoogleJwtPayload {
  sub: string;
  email?: string;
  name?: string;
  picture?: string;
}

export const GoogleLoginBtn = () => {
  const navigate = useNavigate();

  // Lấy redirect URL nếu có
  const params = new URLSearchParams(window.location.search);
  const redirectUrl = params.get("redirect");

  const handleSuccess = async (credentialResponse: any) => {
    try {
      // 1️⃣ Gửi google credential lên backend
      const loginRes = await axiosInstance.post("/account/google-login", {
        token: credentialResponse.credential,
      });

      const token = loginRes.data.access_token;

      // 2️⃣ Decode JWT từ BACKEND
      const decodedBackend = jwtDecode<BackendJwtPayload>(token);

      // 🚫 BLOCK LOGIN
      if (decodedBackend.per === "000") {
        ToastService.error("Tài khoản của bạn đã bị khóa");
        return;
      }

      // 🔥 Nếu có redirect → quay về hệ thống gọi login (giống login thường)
      if (redirectUrl) {
        const separator = redirectUrl.includes("?") ? "&" : "?";
        window.location.href = `${redirectUrl}${separator}token=${token}`;
        return;
      }

      // ✅ Lưu token (chỉ khi login nội bộ, không có redirect)
      localStorage.setItem("token", token);

      // 3️⃣ Decode google token chỉ để lấy email
      const decodedGoogle: GoogleJwtPayload = jwtDecode(
        credentialResponse.credential
      );
      const email = decodedGoogle.email || decodedGoogle.sub;

      // 4️⃣ Lấy account info
      let accountData;
      try {
        accountData = await AccountService.get_account_info(email);
      } catch {
        navigate("/complete-profile");
        return;
      }

      // Nếu chưa có fullName → chuyển đến complete-profile
      if (!accountData.fullName?.trim()) {
        localStorage.setItem("account", JSON.stringify(accountData));
        navigate("/complete-profile");
        return;
      }

      // ✅ Đã có fullName → vào home
      navigate("/home");
    } catch (err) {
      console.error("Google login failed:", err);
      ToastService.error("Đăng nhập Google thất bại");
    }
  };

  return (
    <GoogleLogin
      onSuccess={handleSuccess}
      onError={() => ToastService.error("Google Login Failed")}
    />
  );
};