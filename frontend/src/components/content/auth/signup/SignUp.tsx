import { Link, useNavigate, Navigate } from 'react-router-dom';
import { useState, type ChangeEvent, type FormEvent, useEffect } from 'react';
import { AxiosError } from "axios";
import axiosInstance from '../../../../utils/AxiosInstance';
import { isTokenExpired } from '../../../../utils/Auth';
import { GoogleLoginBtn } from '../google/GoogleLoginBtn';
import logo from "../../../../assets/logo.png";
import './SignUp.css';

type FormData = {
    email: string;
    password: string;
    confirmPassword: string;
}

const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;

function validatePassword(password: string): string | null {
    if (!passwordRegex.test(password)) {
        return "Mật khẩu phải >= 8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt.";
    }
    return null;
}

function SignUp() {
    const token = localStorage.getItem('token');
    if (token && !isTokenExpired(token)) {
        return <Navigate to="/" replace />;
    }

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const [formData, setFormData] = useState<FormData>({
        email: '',
        password: '',
        confirmPassword: ''
    });

    const navigate = useNavigate();

    useEffect(() => {
        document.body.classList.add("login-page");
        return () => {
            document.body.classList.remove("login-page");
        };
    }, []);

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (formData.password !== formData.confirmPassword) {
            setError("Mật khẩu và xác nhận mật khẩu không khớp");
            return;
        }

        const passwordErr = validatePassword(formData.password);
        if (passwordErr) {
            setError(passwordErr);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const response = await axiosInstance.post<{ message: string }>(
                "/account/register/",
                {
                    email: formData.email,
                    password: formData.password,
                }
            );

            const res = response.data.message;
            navigate("/verify-otp", { state: { email: formData.email, message: res } });

        } catch (err) {
            const error = err as AxiosError<{ message: string }>;
            setError(error.response?.data?.message || "Đăng ký thất bại");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-logo">
                    <img src={logo} alt="Logo" className="logo-img" />
                </div>

                <div className="slogan">
                    <span className="slogan-blue">Tạo tài khoản</span>
                    {/* <span className="slogan-blue"> UTEZone</span> */}
                </div>

                <form onSubmit={handleSubmit}>
                    <input
                        type="email"
                        placeholder="Email"
                        name="email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Mật khẩu"
                        name="password"
                        value={formData.password}
                        onChange={handleChange}
                        autoComplete="new-password"
                        required
                    />
                    <input
                        type="password"
                        placeholder="Xác nhận mật khẩu"
                        name="confirmPassword"
                        value={formData.confirmPassword}
                        onChange={handleChange}
                        required
                    />
                    <button className="signin-btn" type="submit" disabled={isLoading}>
                        {isLoading ? 'Đang đăng ký...' : 'Đăng ký'}
                    </button>

                    <div className="create-account" style={{ marginTop: '0' }}>
                        <p style={{ fontSize: '14px', color: '#333' }}>
                            Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
                        </p>
                    </div>
                    {error && <div className="error-message">{error}</div>}
                </form>

                <div className="social-divider">
                    <span>Hoặc</span>
                </div>

                <div className="social-login">
                    <GoogleLoginBtn />
                </div>

                <div className="terms">
                    Copyright © 2026 utezone.site | Powered by utezone.site
                </div>
            </div>
        </div>
    );
}

export default SignUp;