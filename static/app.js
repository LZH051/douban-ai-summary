// 危险操作二次确认
document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
});

// 移动端导航抽屉：展开/收起、Esc 关闭、点击外部关闭、拉宽复位
const navToggle = document.querySelector(".nav-toggle");
const mainNav = document.getElementById("main-nav");
if (navToggle && mainNav) {
    const closeNav = () => {
        mainNav.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
    };
    navToggle.addEventListener("click", () => {
        const open = mainNav.classList.toggle("is-open");
        navToggle.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeNav();
    });
    document.addEventListener("click", (event) => {
        if (
            mainNav.classList.contains("is-open")
            && !mainNav.contains(event.target)
            && !navToggle.contains(event.target)
        ) closeNav();
    });
    window.addEventListener("resize", () => {
        if (window.innerWidth > 580) closeNav();
    });
}

// flash 提示：可手动关闭，6 秒后自动淡出
document.querySelectorAll(".flash").forEach((flash) => {
    const close = document.createElement("button");
    close.type = "button";
    close.className = "flash-close";
    close.setAttribute("aria-label", "关闭提示");
    close.textContent = "×";
    close.addEventListener("click", () => flash.remove());
    flash.appendChild(close);
    setTimeout(() => {
        flash.classList.add("flash-hide");
        setTimeout(() => flash.remove(), 400);
    }, 6000);
});
