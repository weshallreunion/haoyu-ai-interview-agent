const messagesElement =
    document.querySelector("#messages");

const chatForm =
    document.querySelector("#chat-form");

const messageInput =
    document.querySelector("#message-input");

const sendButton =
    document.querySelector("#send-button");

const newChatButton =
    document.querySelector("#new-chat-button");

const suggestionButtons =
    document.querySelectorAll(".suggestion");


const SESSION_STORAGE_KEY =
    "haoyu_ai_session_id";


function createSessionId() {
    const existingSessionId =
        localStorage.getItem(
            SESSION_STORAGE_KEY
        );

    if (existingSessionId) {
        return existingSessionId;
    }

    const randomPart = crypto.randomUUID()
        .replaceAll("-", "")
        .slice(0, 20);

    const newSessionId =
        `recruiter_${randomPart}`;

    localStorage.setItem(
        SESSION_STORAGE_KEY,
        newSessionId
    );

    return newSessionId;
}


let sessionId = createSessionId();


function renderMarkdown(content) {
    const markdownHtml = marked.parse(
        content,
        {
            breaks: true,
            gfm: true
        }
    );

    return DOMPurify.sanitize(
        markdownHtml,
        {
            USE_PROFILES: {
                html: true
            }
        }
    );
}


function isNearBottom() {
    const distanceFromBottom =
        messagesElement.scrollHeight
        - messagesElement.scrollTop
        - messagesElement.clientHeight;

    return distanceFromBottom < 120;
}


function scrollToBottom() {
    messagesElement.scrollTop =
        messagesElement.scrollHeight;
}


function addSourceBadge(
    sourcesElement,
    label
) {
    if (
        !sourcesElement ||
        !label
    ) {
        return;
    }

    const existingBadges =
        sourcesElement.querySelectorAll(
            ".source-badge"
        );

    const alreadyExists = Array.from(
        existingBadges
    ).some(
        (badge) =>
            badge.textContent === label
    );

    if (alreadyExists) {
        return;
    }

    if (sourcesElement.hidden) {
        const headingElement =
            document.createElement("span");

        headingElement.className =
            "sources-heading";

        headingElement.textContent =
            "回答依据";

        sourcesElement.appendChild(
            headingElement
        );

        sourcesElement.hidden = false;
    }

    const badgeElement =
        document.createElement("span");

    badgeElement.className =
        "source-badge";

    badgeElement.textContent = label;

    sourcesElement.appendChild(
        badgeElement
    );
}


function createFeedbackElement() {
    const feedbackElement =
        document.createElement("div");

    feedbackElement.className =
        "message-feedback";

    feedbackElement.hidden = true;


    const labelElement =
        document.createElement("span");

    labelElement.className =
        "feedback-label";

    labelElement.textContent =
        "这条回答有帮助吗？";


    const upButton =
        document.createElement("button");

    upButton.type = "button";
    upButton.className =
        "feedback-button";

    upButton.dataset.rating = "up";
    upButton.textContent = "👍";
    upButton.title = "有帮助";
    upButton.setAttribute(
        "aria-label",
        "这条回答有帮助"
    );


    const downButton =
        document.createElement("button");

    downButton.type = "button";
    downButton.className =
        "feedback-button";

    downButton.dataset.rating = "down";
    downButton.textContent = "👎";
    downButton.title = "没帮助";
    downButton.setAttribute(
        "aria-label",
        "这条回答没帮助"
    );


    const statusElement =
        document.createElement("span");

    statusElement.className =
        "feedback-status";


    feedbackElement.append(
        labelElement,
        upButton,
        downButton,
        statusElement
    );

    return feedbackElement;
}


function setFeedbackState(
    feedbackElement,
    rating
) {
    const buttons =
        feedbackElement.querySelectorAll(
            ".feedback-button"
        );

    buttons.forEach((button) => {
        const isSelected =
            button.dataset.rating === rating;

        button.classList.toggle(
            "selected",
            isSelected
        );

        button.setAttribute(
            "aria-pressed",
            isSelected
                ? "true"
                : "false"
        );
    });

    feedbackElement.dataset.feedback =
        rating || "";
}


function activateFeedbackControls(
    feedbackElement,
    messageId,
    feedback = null
) {
    if (
        !feedbackElement ||
        !Number.isInteger(messageId) ||
        messageId <= 0
    ) {
        return;
    }

    feedbackElement.dataset.messageId =
        String(messageId);

    feedbackElement.hidden = false;

    setFeedbackState(
        feedbackElement,
        feedback
    );
}


function setFeedbackLoading(
    feedbackElement,
    isLoading
) {
    const buttons =
        feedbackElement.querySelectorAll(
            ".feedback-button"
        );

    buttons.forEach((button) => {
        button.disabled = isLoading;
    });
}


function setFeedbackStatus(
    feedbackElement,
    text
) {
    const statusElement =
        feedbackElement.querySelector(
            ".feedback-status"
        );

    if (statusElement) {
        statusElement.textContent = text;
    }
}


function createMessage(
    role,
    content = "",
    options = {}
) {
    const sources =
        Array.isArray(options.sources)
            ? options.sources
            : [];

    const messageId =
        Number.isInteger(
            options.messageId
        )
            ? options.messageId
            : null;

    const feedback =
        options.feedback === "up"
        || options.feedback === "down"
            ? options.feedback
            : null;

    const enableFeedback =
        options.enableFeedback === true;


    const messageElement =
        document.createElement("div");

    messageElement.className =
        role === "user"
            ? "message user-message"
            : "message assistant-message";


    const labelElement =
        document.createElement("div");

    labelElement.className =
        "message-label";

    labelElement.textContent =
        role === "user"
            ? "Recruiter"
            : "Haoyu AI";


    const contentElement =
        document.createElement("div");

    contentElement.className =
        "message-content";


    if (role === "assistant") {
        contentElement.innerHTML =
            renderMarkdown(content);
    } else {
        contentElement.textContent =
            content;
    }


    const sourcesElement =
        document.createElement("div");

    sourcesElement.className =
        "message-sources";

    sourcesElement.hidden = true;


    const feedbackElement =
        createFeedbackElement();


    messageElement.append(
        labelElement,
        contentElement
    );


    if (role === "assistant") {
        messageElement.append(
            sourcesElement,
            feedbackElement
        );

        sources.forEach((source) => {
            addSourceBadge(
                sourcesElement,
                source
            );
        });

        if (
            enableFeedback &&
            messageId !== null
        ) {
            activateFeedbackControls(
                feedbackElement,
                messageId,
                feedback
            );
        }
    }


    messagesElement.appendChild(
        messageElement
    );

    scrollToBottom();

    return {
        messageElement,
        contentElement,
        sourcesElement,
        feedbackElement
    };
}


function addMessage(
    role,
    content,
    options = {}
) {
    return createMessage(
        role,
        content,
        options
    );
}


function setLoading(isLoading) {
    sendButton.disabled = isLoading;
    messageInput.disabled = isLoading;
    newChatButton.disabled = isLoading;

    suggestionButtons.forEach((button) => {
        button.disabled = isLoading;
    });

    sendButton.textContent =
        isLoading
            ? "思考中"
            : "发送";
}


function resetMessages() {
    messagesElement.replaceChildren();

    addMessage(
        "assistant",
        "你好，我是 Haoyu AI。" +
        "你可以把我理解成钱浩宇的数字简历，" +
        "直接和我聊项目、技术方向、" +
        "学习经历和实习安排。",
        {
            enableFeedback: false
        }
    );
}


async function getResponseErrorMessage(
    response
) {
    let serverDetail = "";

    try {
        const errorData =
            await response.json();

        if (
            typeof errorData.detail
            === "string"
        ) {
            serverDetail =
                errorData.detail;
        }

    } catch (error) {
        console.debug(
            "错误响应不是JSON：",
            error
        );
    }


    if (response.status === 429) {
        const retryAfter =
            response.headers.get(
                "Retry-After"
            );

        if (retryAfter) {
            return (
                "请求过于频繁，请在 " +
                retryAfter +
                " 秒后重新尝试。"
            );
        }

        return (
            serverDetail ||
            "请求过于频繁，请稍后重新尝试。"
        );
    }


    if (response.status === 409) {
        return (
            serverDetail ||
            "当前对话已有回答正在生成，" +
            "请等待完成后再发送。"
        );
    }


    if (response.status === 422) {
        return "发送的内容格式不正确。";
    }


    return (
        serverDetail ||
        "请求失败，状态码：" +
        response.status
    );
}


async function loadConversationHistory() {
    setLoading(true);

    try {
        const encodedSessionId =
            encodeURIComponent(sessionId);

        const response = await fetch(
            `/chat/history/${encodedSessionId}`,
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                await getResponseErrorMessage(
                    response
                )
            );
        }

        const data = await response.json();

        messagesElement.replaceChildren();

        if (
            !Array.isArray(data.messages) ||
            data.messages.length === 0
        ) {
            resetMessages();
            return;
        }

        data.messages.forEach((message) => {
            if (
                message.role !== "user" &&
                message.role !== "assistant"
            ) {
                return;
            }

            const sources =
                Array.isArray(message.sources)
                    ? message.sources
                    : [];

            const messageId =
                Number.isInteger(
                    message.message_id
                )
                    ? message.message_id
                    : null;

            addMessage(
                message.role,
                message.content,
                {
                    sources: sources,
                    messageId: messageId,
                    feedback: message.feedback,
                    enableFeedback:
                        message.role ===
                            "assistant"
                        && messageId !== null
                }
            );
        });

        scrollToBottom();

    } catch (error) {
        console.error(
            "加载聊天历史失败：",
            error
        );

        resetMessages();

    } finally {
        setLoading(false);
        messageInput.focus();
    }
}


async function startNewConversation() {
    const previousSessionId = sessionId;

    setLoading(true);

    try {
        const encodedSessionId =
            encodeURIComponent(
                previousSessionId
            );

        const response = await fetch(
            `/chat/history/${encodedSessionId}`,
            {
                method: "DELETE"
            }
        );

        if (
            !response.ok &&
            response.status !== 404
        ) {
            throw new Error(
                await getResponseErrorMessage(
                    response
                )
            );
        }

    } catch (error) {
        console.error(
            "清空旧会话失败：",
            error
        );

    } finally {
        localStorage.removeItem(
            SESSION_STORAGE_KEY
        );

        sessionId = createSessionId();

        resetMessages();

        messageInput.value = "";

        setLoading(false);

        messageInput.focus();
    }
}


async function submitFeedback(
    feedbackElement,
    rating
) {
    const messageId = Number(
        feedbackElement.dataset.messageId
    );

    if (
        !Number.isInteger(messageId) ||
        messageId <= 0
    ) {
        return;
    }

    const currentRating =
        feedbackElement.dataset.feedback;

    if (currentRating === rating) {
        return;
    }

    setFeedbackLoading(
        feedbackElement,
        true
    );

    setFeedbackStatus(
        feedbackElement,
        "提交中……"
    );

    try {
        const response = await fetch(
            "/chat/feedback",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    session_id: sessionId,
                    message_id: messageId,
                    rating: rating
                })
            }
        );

        if (!response.ok) {
            throw new Error(
                await getResponseErrorMessage(
                    response
                )
            );
        }

        const data = await response.json();

        setFeedbackState(
            feedbackElement,
            data.rating
        );

        setFeedbackStatus(
            feedbackElement,
            "已记录"
        );

        window.setTimeout(() => {
            setFeedbackStatus(
                feedbackElement,
                ""
            );
        }, 1800);

    } catch (error) {
        console.error(
            "提交反馈失败：",
            error
        );

        setFeedbackStatus(
            feedbackElement,
            "提交失败"
        );

    } finally {
        setFeedbackLoading(
            feedbackElement,
            false
        );
    }
}


async function sendMessage(message) {
    addMessage(
        "user",
        message
    );

    const assistantMessage =
        createMessage(
            "assistant",
            "",
            {
                enableFeedback: false
            }
        );

    const assistantContent =
        assistantMessage.contentElement;

    const sourcesElement =
        assistantMessage.sourcesElement;

    const feedbackElement =
        assistantMessage.feedbackElement;


    assistantContent.textContent =
        "正在查找已确认资料……";

    assistantContent.classList.add(
        "streaming"
    );

    setLoading(true);


    let fullAnswer = "";
    let streamBuffer = "";


    function handleStreamEvent(eventData) {
        if (eventData.type === "source") {
            addSourceBadge(
                sourcesElement,
                eventData.label
            );

            return;
        }


        if (eventData.type === "text") {
            fullAnswer +=
                eventData.delta || "";

            assistantContent.innerHTML =
                renderMarkdown(
                    fullAnswer
                );

            return;
        }


        if (eventData.type === "done") {
            const finalSources =
                Array.isArray(
                    eventData.sources
                )
                    ? eventData.sources
                    : [];

            finalSources.forEach((source) => {
                addSourceBadge(
                    sourcesElement,
                    source
                );
            });

            if (
                Number.isInteger(
                    eventData.message_id
                )
            ) {
                activateFeedbackControls(
                    feedbackElement,
                    eventData.message_id,
                    null
                );
            }

            return;
        }


        if (eventData.type === "error") {
            throw new Error(
                eventData.message ||
                "Agent运行失败。"
            );
        }
    }


    function processCompleteLines(
        flush = false
    ) {
        const lines =
            streamBuffer.split("\n");

        if (flush) {
            streamBuffer = "";
        } else {
            streamBuffer =
                lines.pop() || "";
        }

        for (const line of lines) {
            const trimmedLine =
                line.trim();

            if (!trimmedLine) {
                continue;
            }

            const eventData =
                JSON.parse(
                    trimmedLine
                );

            handleStreamEvent(
                eventData
            );
        }
    }


    try {
        const response = await fetch(
            "/chat/stream",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    session_id: sessionId,
                    message: message
                })
            }
        );


        if (!response.ok) {
            throw new Error(
                await getResponseErrorMessage(
                    response
                )
            );
        }


        if (!response.body) {
            throw new Error(
                "浏览器没有收到流式响应。"
            );
        }


        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder("utf-8");


        while (true) {
            const shouldFollow =
                isNearBottom();

            const {
                done,
                value
            } = await reader.read();


            if (done) {
                break;
            }


            streamBuffer += decoder.decode(
                value,
                {
                    stream: true
                }
            );


            processCompleteLines();


            if (shouldFollow) {
                scrollToBottom();
            }
        }


        streamBuffer += decoder.decode();


        if (streamBuffer.trim()) {
            streamBuffer += "\n";

            processCompleteLines(true);
        }


        if (!fullAnswer.trim()) {
            assistantContent.textContent =
                "没有收到有效回答，请重新尝试。";
        } else {
            assistantContent.innerHTML =
                renderMarkdown(
                    fullAnswer
                );
        }

    } catch (error) {
        console.error(
            "发送消息失败：",
            error
        );

        const errorMessage =
            error instanceof Error
                ? error.message
                : "未知错误";

        if (fullAnswer.trim()) {
            fullAnswer += (
                "\n\n> 回答传输中断：" +
                errorMessage
            );

            assistantContent.innerHTML =
                renderMarkdown(
                    fullAnswer
                );
        } else {
            assistantContent.textContent =
                errorMessage;
        }

    } finally {
        assistantContent.classList.remove(
            "streaming"
        );

        setLoading(false);

        messageInput.focus();

        scrollToBottom();
    }
}


chatForm.addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const message =
            messageInput.value.trim();

        if (!message) {
            return;
        }

        messageInput.value = "";

        await sendMessage(message);
    }
);


messageInput.addEventListener(
    "keydown",
    (event) => {
        const shouldSend =
            event.key === "Enter"
            && !event.shiftKey
            && !event.isComposing;

        if (shouldSend) {
            event.preventDefault();

            chatForm.requestSubmit();
        }
    }
);


suggestionButtons.forEach((button) => {
    button.addEventListener(
        "click",
        async () => {
            const message =
                button.textContent.trim();

            await sendMessage(message);
        }
    );
});


messagesElement.addEventListener(
    "click",
    async (event) => {
        if (
            !(event.target instanceof Element)
        ) {
            return;
        }

        const button = event.target.closest(
            ".feedback-button"
        );

        if (!button) {
            return;
        }

        const feedbackElement =
            button.closest(
                ".message-feedback"
            );

        if (!feedbackElement) {
            return;
        }

        const rating =
            button.dataset.rating;

        if (
            rating !== "up" &&
            rating !== "down"
        ) {
            return;
        }

        await submitFeedback(
            feedbackElement,
            rating
        );
    }
);


newChatButton.addEventListener(
    "click",
    startNewConversation
);


loadConversationHistory();