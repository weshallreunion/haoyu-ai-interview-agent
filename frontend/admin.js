const TOKEN_STORAGE_KEY =
    "haoyu_admin_token";

const loginPanel =
    document.querySelector("#login-panel");

const dashboard =
    document.querySelector("#dashboard");

const tokenInput =
    document.querySelector("#token-input");

const loginButton =
    document.querySelector("#login-button");

const logoutButton =
    document.querySelector("#logout-button");

const refreshButton =
    document.querySelector("#refresh-button");

const loginStatus =
    document.querySelector("#login-status");

const dashboardStatus =
    document.querySelector("#dashboard-status");

const feedbackList =
    document.querySelector("#feedback-list");

const filterButtons =
    document.querySelectorAll(
        ".filter-button"
    );

const totalCount =
    document.querySelector("#total-count");

const upCount =
    document.querySelector("#up-count");

const downCount =
    document.querySelector("#down-count");

const satisfactionRate =
    document.querySelector(
        "#satisfaction-rate"
    );


let currentRating = "";


function getStoredToken() {
    return (
        sessionStorage.getItem(
            TOKEN_STORAGE_KEY
        ) || ""
    );
}


function setStatus(
    element,
    message,
    type = ""
) {
    element.textContent = message;
    element.dataset.type = type;
}


async function readErrorMessage(
    response
) {
    try {
        const data = await response.json();

        if (
            typeof data.detail === "string"
        ) {
            return data.detail;
        }
    } catch (error) {
        console.debug(
            "管理接口错误响应不是JSON：",
            error
        );
    }

    return (
        "请求失败，状态码：" +
        response.status
    );
}


async function adminFetch(path) {
    const token = getStoredToken();

    if (!token) {
        throw new Error(
            "请先输入管理员密钥。"
        );
    }

    const response = await fetch(
        path,
        {
            headers: {
                "Authorization":
                    `Bearer ${token}`
            },
            cache: "no-store"
        }
    );

    if (!response.ok) {
        const message =
            await readErrorMessage(
                response
            );

        if (response.status === 401) {
            sessionStorage.removeItem(
                TOKEN_STORAGE_KEY
            );
        }

        throw new Error(message);
    }

    return response.json();
}


function renderSummary(summary) {
    totalCount.textContent =
        String(summary.total ?? 0);

    upCount.textContent =
        String(summary.up_count ?? 0);

    downCount.textContent =
        String(summary.down_count ?? 0);

    satisfactionRate.textContent =
        `${summary.satisfaction_rate ?? 0}%`;
}


function formatDate(value) {
    if (!value) {
        return "未知时间";
    }

    const normalizedValue =
        value.replace(" ", "T") + "Z";

    const date = new Date(
        normalizedValue
    );

    if (
        Number.isNaN(date.getTime())
    ) {
        return value;
    }

    return date.toLocaleString(
        "zh-CN"
    );
}


function createTextSection(
    title,
    content
) {
    const section =
        document.createElement("section");

    section.className =
        "record-text-section";

    const heading =
        document.createElement("h3");

    heading.textContent = title;

    const paragraph =
        document.createElement("p");

    paragraph.textContent =
        content || "无";

    section.append(
        heading,
        paragraph
    );

    return section;
}


function renderRecords(records) {
    feedbackList.replaceChildren();

    if (
        !Array.isArray(records) ||
        records.length === 0
    ) {
        const emptyElement =
            document.createElement("p");

        emptyElement.className =
            "empty-state";

        emptyElement.textContent =
            "当前没有符合条件的反馈。";

        feedbackList.appendChild(
            emptyElement
        );

        return;
    }

    records.forEach((record) => {
        const article =
            document.createElement("article");

        article.className =
            "feedback-record";


        const header =
            document.createElement("header");

        header.className =
            "record-header";


        const ratingBadge =
            document.createElement("span");

        ratingBadge.className =
            record.rating === "up"
                ? "rating-badge positive"
                : "rating-badge negative";

        ratingBadge.textContent =
            record.rating === "up"
                ? "👍 有帮助"
                : "👎 没帮助";


        const metadata =
            document.createElement("span");

        metadata.className =
            "record-metadata";

        metadata.textContent =
            `${record.session_id} · `
            + formatDate(
                record.updated_at
            );


        header.append(
            ratingBadge,
            metadata
        );


        article.append(
            header,
            createTextSection(
                "用户问题",
                record.question
            ),
            createTextSection(
                "Agent 回答",
                record.answer
            )
        );


        if (
            Array.isArray(record.sources) &&
            record.sources.length > 0
        ) {
            const sourcesContainer =
                document.createElement("div");

            sourcesContainer.className =
                "record-sources";

            record.sources.forEach(
                (source) => {
                    const badge =
                        document.createElement(
                            "span"
                        );

                    badge.className =
                        "source-badge";

                    badge.textContent =
                        source;

                    sourcesContainer.appendChild(
                        badge
                    );
                }
            );

            article.appendChild(
                sourcesContainer
            );
        }


        if (record.comment) {
            article.appendChild(
                createTextSection(
                    "补充意见",
                    record.comment
                )
            );
        }


        feedbackList.appendChild(
            article
        );
    });
}


async function loadDashboard() {
    setStatus(
        dashboardStatus,
        "正在加载反馈数据……"
    );

    refreshButton.disabled = true;

    try {
        const ratingQuery =
            currentRating
                ? `&rating=${encodeURIComponent(
                    currentRating
                )}`
                : "";

        const [
            summary,
            records
        ] = await Promise.all([
            adminFetch(
                "/admin/api/feedback/summary"
            ),
            adminFetch(
                "/admin/api/feedback/recent"
                + `?limit=50${ratingQuery}`
            )
        ]);

        renderSummary(summary);
        renderRecords(records);

        loginPanel.hidden = true;
        dashboard.hidden = false;
        logoutButton.hidden = false;

        setStatus(
            dashboardStatus,
            `已加载 ${records.length} 条反馈`,
            "success"
        );

    } catch (error) {
        console.error(
            "加载后台失败：",
            error
        );

        const message =
            error instanceof Error
                ? error.message
                : "后台加载失败。";

        setStatus(
            loginStatus,
            message,
            "error"
        );

        loginPanel.hidden = false;
        dashboard.hidden = true;
        logoutButton.hidden = true;

    } finally {
        refreshButton.disabled = false;
    }
}


async function login() {
    const token =
        tokenInput.value.trim();

    if (!token) {
        setStatus(
            loginStatus,
            "请输入管理员密钥。",
            "error"
        );

        return;
    }

    sessionStorage.setItem(
        TOKEN_STORAGE_KEY,
        token
    );

    setStatus(
        loginStatus,
        "正在验证……"
    );

    await loadDashboard();
}


function logout() {
    sessionStorage.removeItem(
        TOKEN_STORAGE_KEY
    );

    tokenInput.value = "";

    dashboard.hidden = true;
    logoutButton.hidden = true;
    loginPanel.hidden = false;

    feedbackList.replaceChildren();

    setStatus(
        loginStatus,
        "已退出管理后台。",
        "success"
    );

    tokenInput.focus();
}


loginButton.addEventListener(
    "click",
    login
);


tokenInput.addEventListener(
    "keydown",
    (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            login();
        }
    }
);


logoutButton.addEventListener(
    "click",
    logout
);


refreshButton.addEventListener(
    "click",
    loadDashboard
);


filterButtons.forEach((button) => {
    button.addEventListener(
        "click",
        async () => {
            currentRating =
                button.dataset.rating || "";

            filterButtons.forEach(
                (targetButton) => {
                    targetButton.classList.toggle(
                        "active",
                        targetButton === button
                    );
                }
            );

            await loadDashboard();
        }
    );
});


if (getStoredToken()) {
    loadDashboard();
} else {
    tokenInput.focus();
}