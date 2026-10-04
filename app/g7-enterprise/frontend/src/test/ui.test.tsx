import { fireEvent, render, screen } from "@testing-library/react";
import { Login } from "../components/Login";

describe("Login", () => {
  it("renders the sign-in form, demo users, and the disclaimer", () => {
    render(<Login onLoggedIn={() => {}} />);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "reviewer@demo" })).toBeInTheDocument();
    expect(screen.getByText(/Not for diagnosis/i)).toBeInTheDocument();
  });

  it("prefills a demo email into the field when a chip is clicked", () => {
    render(<Login onLoggedIn={() => {}} />);
    const input = screen.getByLabelText("email") as HTMLInputElement;
    expect(input.value).toBe("reviewer@demo");
    fireEvent.click(screen.getByRole("button", { name: "auditor@demo" }));
    expect(input.value).toBe("auditor@demo");
  });
});
