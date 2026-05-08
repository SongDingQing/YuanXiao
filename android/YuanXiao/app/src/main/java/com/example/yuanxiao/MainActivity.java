package com.example.yuanxiao;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Html;
import android.text.InputType;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.net.ssl.HttpsURLConnection;

public class MainActivity extends Activity {
    private static final String RELAY_BASE_URL = normalizeRelayBaseUrl(BuildConfig.YUANXIAO_RELAY_BASE_URL);
    private static final String CHAT_URL = endpoint("/api/chat");
    private static final String HEALTH_URL = endpoint("/health");
    private static final String INBOX_URL = endpoint("/api/inbox");
    private static final String CODEX_DASHBOARD_URL = endpoint("/api/codex/sessions?limit=50");
    private static final String CODEX_SESSION_MESSAGES_URL = endpoint("/api/codex/session/messages");
    private static final String CODEX_SESSION_CREATE_URL = endpoint("/api/codex/session/create");
    private static final String CODEX_SESSION_RENAME_URL = endpoint("/api/codex/session/rename");
    private static final String PLAN_PROJECTS_URL = endpoint("/api/plan/projects?limit=30");
    private static final String NOTIFICATION_CHANNEL_ID = "yuanxiao_messages";
    private static final String PREFS_NAME = "yuanxiao_state";
    private static final String KEY_LAST_INBOX_ID = "last_inbox_id";
    private static final String KEY_CHAT_TARGET = "chat_target";
    private static final String KEY_CODEX_SESSION_ID = "codex_session_id";
    private static final String KEY_CODEX_SESSION_TITLE = "codex_session_title";
    private static final String KEY_MAIN_CHAT_HISTORY = "main_chat_history";
    private static final String TARGET_HERMES = "hermes";
    private static final String TARGET_CODEX = "codex";
    private static final String TAB_HERMES = "hermes";
    private static final String TAB_CODEX = "codex";
    private static final String TAB_PLAN = "plan";
    private static final String MAIN_CHAT_CONVERSATION = "yuanxiao-change-main";
    private static final int REQUEST_PICK_IMAGE = 1001;
    private static final int REQUEST_POST_NOTIFICATIONS = 1002;
    private static final int MAX_HERMES_IMAGE_BYTES = 650_000;
    private static final int MAX_IMAGE_EDGE = 960;
    private static final int MAX_LOG_LINES = 120;
    private static final int MAX_RICH_TEXT_CACHE_ENTRIES = 160;
    private static final int MAX_MAIN_CHAT_HISTORY_MESSAGES = 180;
    private static final int MAX_MAIN_CHAT_HISTORY_TEXT_CHARS = 6000;
    private static final int MAX_MAIN_CHAT_ATTACHMENT_DATA_CHARS = 24000;
    private static final int MAX_SESSION_HISTORY_MESSAGES = 240;
    private static final long INBOX_POLL_INTERVAL_MS = 15_000L;
    private static final long DASHBOARD_POLL_INTERVAL_MS = 15_000L;
    private static final long SESSION_CHAT_POLL_INTERVAL_MS = 15_000L;
    private static final long PLAN_POLL_INTERVAL_MS = 20_000L;
    private static final Pattern MARKDOWN_IMAGE_PATTERN = Pattern.compile("!\\[([^\\]]*)]\\(([^)\\s]+)(?:\\s+\"[^\"]*\")?\\)");
    private static final Pattern MARKDOWN_LINK_PATTERN = Pattern.compile("\\[([^\\]]+)]\\((https?://[^)\\s]+)(?:\\s+\"[^\"]*\")?\\)");
    private static final Pattern RAW_URL_PATTERN = Pattern.compile("https?://\\S+");
    private static final Pattern FILE_URL_PATTERN = Pattern.compile("(?i)\\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|md|csv|zip|rar|7z|apk|mp4|mov|mp3|wav|png|jpg|jpeg|webp|gif)(\\?|#|$)");

    private static String normalizeRelayBaseUrl(String value) {
        String baseUrl = value == null ? "" : value.trim();
        if (baseUrl.isEmpty()) {
            baseUrl = "https://a.example.com";
        }
        while (baseUrl.endsWith("/")) {
            baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
        }
        return baseUrl;
    }

    private static String endpoint(String path) {
        return RELAY_BASE_URL + path;
    }

    private TextView noticeBanner;
    private final ExecutorService executor = Executors.newFixedThreadPool(2);
    private final Handler inboxHandler = new Handler(Looper.getMainLooper());
    private final Handler dashboardHandler = new Handler(Looper.getMainLooper());
    private final Handler sessionChatHandler = new Handler(Looper.getMainLooper());
    private final Handler planHandler = new Handler(Looper.getMainLooper());
    private final Handler noticeHandler = new Handler(Looper.getMainLooper());
    private final Runnable hideNoticeRunnable = () -> {
        if (noticeBanner != null) {
            noticeBanner.setVisibility(View.GONE);
        }
    };
    private final Runnable inboxPollRunnable = new Runnable() {
        @Override
        public void run() {
            if (!inboxPolling) {
                return;
            }
            pollInboxOnce();
            inboxHandler.postDelayed(this, INBOX_POLL_INTERVAL_MS);
        }
    };
    private final Runnable dashboardPollRunnable = new Runnable() {
        @Override
        public void run() {
            if (!dashboardVisible) {
                return;
            }
            pollCodexDashboard();
            dashboardHandler.postDelayed(this, DASHBOARD_POLL_INTERVAL_MS);
        }
    };
    private final Runnable sessionChatPollRunnable = new Runnable() {
        @Override
        public void run() {
            if (!sessionChatVisible) {
                return;
            }
            syncCurrentSessionMessages(false);
            sessionChatHandler.postDelayed(this, SESSION_CHAT_POLL_INTERVAL_MS);
        }
    };
    private final Runnable planPollRunnable = new Runnable() {
        @Override
        public void run() {
            if (!planVisible) {
                return;
            }
            pollPlanView();
            planHandler.postDelayed(this, PLAN_POLL_INTERVAL_MS);
        }
    };
    private LinearLayout chatView;
    private LinearLayout sessionChatView;
    private LinearLayout dashboardView;
    private LinearLayout planView;
    private LinearLayout bottomTabBar;
    private LinearLayout dashboardSessionList;
    private TextView dashboardSummary;
    private TextView dashboardUpdated;
    private TextView dashboardCreateButton;
    private LinearLayout planProjectList;
    private TextView planSummary;
    private TextView planUpdated;
    private TextView hermesTabButton;
    private TextView codexTabButton;
    private TextView planTabButton;
    private ScrollView scrollView;
    private LinearLayout messageList;
    private ScrollView sessionScrollView;
    private LinearLayout sessionMessageList;
    private TextView sessionTitle;
    private TextView sessionSubtitle;
    private TextView sessionRenameButton;
    private TextView logButton;
    private TextView changeLogButton;
    private TextView menuButton;
    private LinearLayout menuPanel;
    private ScrollView changeLogPanel;
    private LinearLayout changeLogList;
    private ScrollView logPanel;
    private TextView logText;
    private EditText input;
    private LinearLayout selectedImagePanel;
    private ImageView selectedImagePreview;
    private TextView selectedImageLabel;
    private TextView imageButton;
    private TextView clearImageButton;
    private TextView sendButton;
    private TextView healthButton;
    private TextView composerOptionsButton;
    private LinearLayout composerOptionsPanel;
    private TextView hermesTargetButton;
    private TextView codexTargetButton;
    private TextView deliveryStatusBar;
    private TextView codexSessionLabel;
    private TextView clearCodexSessionButton;
    private EditText sessionInput;
    private TextView sessionDeliveryStatusBar;
    private TextView sessionSendButton;
    private TextView sessionClearButton;

    private String pendingImageBase64;
    private String pendingImageMimeType;
    private Bitmap pendingImageBitmap;
    private int notificationId = 2000;
    private int logCount = 0;
    private boolean logPanelVisible = false;
    private boolean changeLogPanelVisible = false;
    private boolean menuPanelVisible = false;
    private boolean composerOptionsVisible = false;
    private boolean inboxPolling = false;
    private boolean inboxErrorLogged = false;
    private boolean dashboardVisible = false;
    private boolean sessionChatVisible = false;
    private boolean planVisible = false;
    private boolean dashboardErrorLogged = false;
    private boolean planErrorLogged = false;
    private boolean dashboardActiveExpanded = true;
    private boolean dashboardRecentExpanded = true;
    private boolean dashboardIdleExpanded = true;
    private boolean dashboardArchivedExpanded = false;
    private boolean sessionSyncErrorLogged = false;
    private volatile boolean inboxSyncInFlight = false;
    private volatile boolean dashboardSyncInFlight = false;
    private volatile boolean sessionSyncInFlight = false;
    private volatile boolean planSyncInFlight = false;
    private volatile boolean sessionSendInFlight = false;
    private String lastInboxMessageId = "";
    private String selectedChatTarget = TARGET_HERMES;
    private String selectedCodexSessionId = "";
    private String selectedCodexSessionTitle = "";
    private JSONObject lastDashboardResponse;
    private final List<ReleaseGroup> releaseGroups = new ArrayList<>();
    private final List<ChatRecord> chatRecords = new ArrayList<>();
    private final List<ChatRecord> sessionChatRecords = new ArrayList<>();
    private final List<MainChatMessage> mainChatHistory = new ArrayList<>();
    private final List<String> logLines = new ArrayList<>();
    private final List<String> richTextCacheKeys = new ArrayList<>();
    private final Map<String, Spanned> richTextCache = new HashMap<>();
    private final Map<String, List<SessionChatMessage>> sessionChatHistories = new HashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createNotificationChannel();
        requestNotificationPermissionIfNeeded();
        SharedPreferences preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        lastInboxMessageId = preferences.getString(KEY_LAST_INBOX_ID, "");
        selectedChatTarget = normalizeChatTarget(preferences.getString(KEY_CHAT_TARGET, TARGET_HERMES));
        selectedCodexSessionId = preferences.getString(KEY_CODEX_SESSION_ID, "");
        selectedCodexSessionTitle = preferences.getString(KEY_CODEX_SESSION_TITLE, "");
        seedChangeLog();
        buildUi();
        loadMainChatHistory();
        renderMainChatHistory();
        appendLog("元宵已连接到嫦娥服务器。");
        appendLog("普通文字默认交给 Hermes，专业问题可切到 Codex。");
        appendLog("图片会进入嫦娥识图链路。");
        appendLog("嫦娥的新回复会触发手机通知。");
        appendLog("元宵会自动接收嫦娥主动下发的消息。");
        showChat();
        startInboxPolling();
    }

    @Override
    protected void onDestroy() {
        stopInboxPolling();
        stopDashboardPolling();
        stopSessionChatPolling();
        stopPlanPolling();
        executor.shutdownNow();
        super.onDestroy();
    }

    @Override
    protected void onResume() {
        super.onResume();
        requestNotificationPermissionIfNeeded();
        pollInboxOnce();
        if (dashboardVisible) {
            pollCodexDashboard();
        }
        if (sessionChatVisible) {
            syncCurrentSessionMessages(false);
        }
        if (planVisible) {
            pollPlanView();
        }
    }

    @Override
    public void onBackPressed() {
        if (sessionChatVisible) {
            showDashboard();
            return;
        }
        if (dashboardVisible || planVisible) {
            showChat();
            return;
        }
        super.onBackPressed();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_POST_NOTIFICATIONS) {
            return;
        }
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            appendLog("通知权限已开启，嫦娥新消息可以弹窗提醒了。");
        } else {
            appendLog("通知权限未开启，手机可能不会弹出嫦娥新消息。");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_PICK_IMAGE || resultCode != RESULT_OK || data == null || data.getData() == null) {
            return;
        }
        Uri imageUri = data.getData();
        try {
            getContentResolver().takePersistableUriPermission(imageUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (Exception ignored) {
            // Some pickers grant only a transient read permission, which is enough for immediate sending.
        }
        setBusy(true);
        appendLog("正在处理图片...");
        executor.execute(() -> {
            try {
                ImagePayload imagePayload = buildImagePayload(imageUri);
                runOnUiThread(() -> setSelectedImage(imagePayload));
            } catch (Exception exception) {
                appendLogFromWorker("图片处理失败：" + exception.getMessage());
            } finally {
                runOnUiThread(() -> setBusy(false));
            }
        });
    }

    private void buildUi() {
        LinearLayout screenRoot = new LinearLayout(this);
        screenRoot.setOrientation(LinearLayout.VERTICAL);
        screenRoot.setBackgroundColor(Color.rgb(246, 247, 251));

        noticeBanner = new TextView(this);
        noticeBanner.setVisibility(View.GONE);
        noticeBanner.setTextSize(14);
        noticeBanner.setTypeface(Typeface.DEFAULT_BOLD);
        noticeBanner.setTextColor(Color.rgb(28, 38, 56));
        noticeBanner.setSingleLine(false);
        noticeBanner.setGravity(Gravity.CENTER_VERTICAL);
        noticeBanner.setPadding(dp(14), dp(10), dp(14), dp(10));
        noticeBanner.setBackground(makePanelBackground(Color.rgb(255, 247, 220), 0, 0, Color.TRANSPARENT));
        screenRoot.addView(noticeBanner, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        dashboardView = buildDashboardView();
        dashboardView.setVisibility(View.GONE);
        screenRoot.addView(dashboardView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        ));

        planView = buildPlanView();
        planView.setVisibility(View.GONE);
        screenRoot.addView(planView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        ));

        sessionChatView = buildSessionChatView();
        sessionChatView.setVisibility(View.GONE);
        screenRoot.addView(sessionChatView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        ));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(12), dp(12), dp(10));
        root.setBackgroundColor(Color.rgb(246, 247, 251));
        chatView = root;
        screenRoot.addView(chatView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        ));

        LinearLayout headerCard = new LinearLayout(this);
        headerCard.setOrientation(LinearLayout.VERTICAL);
        headerCard.setPadding(dp(14), dp(12), dp(14), dp(12));
        headerCard.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(228, 233, 241)));
        root.addView(headerCard, matchWrap());

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);
        titleBlock.setPadding(0, 0, dp(8), 0);

        TextView title = new TextView(this);
        title.setText("嫦娥");
        title.setTextSize(23);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(26, 32, 43));
        titleBlock.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("和嫦娥沟通");
        subtitle.setTextSize(13);
        subtitle.setTextColor(Color.rgb(91, 101, 116));
        titleBlock.addView(subtitle);
        header.addView(titleBlock, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView status = makeBadge("在线", Color.rgb(232, 247, 240), Color.rgb(20, 120, 82));
        header.addView(status, new LinearLayout.LayoutParams(dp(62), dp(34)));
        headerCard.addView(header, matchWrap());

        LinearLayout headerTools = new LinearLayout(this);
        headerTools.setOrientation(LinearLayout.HORIZONTAL);
        headerTools.setGravity(Gravity.CENTER_VERTICAL);
        headerTools.setPadding(0, dp(10), 0, 0);

        changeLogButton = makeActionChip("记录", Color.rgb(247, 241, 226), Color.rgb(111, 78, 24));
        changeLogButton.setOnClickListener(view -> toggleChangeLogPanel());
        headerTools.addView(changeLogButton, weightedWrap(1f));

        logButton = makeActionChip("日志", Color.rgb(236, 243, 249), Color.rgb(38, 83, 111));
        logButton.setOnClickListener(view -> toggleLogPanel());
        LinearLayout.LayoutParams logButtonParams = weightedWrap(1f);
        logButtonParams.leftMargin = dp(8);
        headerTools.addView(logButton, logButtonParams);

        TextView versionBadge = makeActionChip("v0.29", Color.rgb(31, 111, 235), Color.WHITE);
        LinearLayout.LayoutParams versionParams = weightedWrap(1f);
        versionParams.leftMargin = dp(8);
        headerTools.addView(versionBadge, versionParams);

        menuButton = makeActionChip("菜单 ▼", Color.rgb(244, 247, 252), Color.rgb(62, 75, 96));
        menuButton.setOnClickListener(view -> toggleMenuPanel());
        LinearLayout.LayoutParams menuButtonParams = weightedWrap(1f);
        menuButtonParams.leftMargin = dp(8);
        headerTools.addView(menuButton, menuButtonParams);
        headerCard.addView(headerTools, matchWrap());
        updateChangeLogButton();
        updateMenuButton();

        menuPanel = new LinearLayout(this);
        menuPanel.setOrientation(LinearLayout.VERTICAL);
        menuPanel.setPadding(dp(12), dp(10), dp(12), dp(10));
        menuPanel.setBackground(makePanelBackground(Color.WHITE, dp(16), 1, Color.rgb(228, 233, 241)));
        menuPanel.setVisibility(View.GONE);
        LinearLayout menuSearchButton = new LinearLayout(this);
        menuSearchButton.setOrientation(LinearLayout.VERTICAL);
        menuSearchButton.setPadding(dp(12), dp(10), dp(12), dp(10));
        menuSearchButton.setBackground(makePanelBackground(Color.rgb(246, 248, 252), dp(14), 1, Color.rgb(229, 234, 242)));
        TextView menuSearchTitle = new TextView(this);
        menuSearchTitle.setText("聊天记录搜索");
        menuSearchTitle.setTextSize(15);
        menuSearchTitle.setTypeface(Typeface.DEFAULT_BOLD);
        menuSearchTitle.setTextColor(Color.rgb(29, 36, 48));
        menuSearchButton.addView(menuSearchTitle);
        TextView menuSearchDesc = new TextView(this);
        menuSearchDesc.setText("跳转到独立页面查找历史聊天内容");
        menuSearchDesc.setTextSize(12);
        menuSearchDesc.setTextColor(Color.rgb(104, 112, 126));
        menuSearchButton.addView(menuSearchDesc);
        menuSearchButton.setOnClickListener(view -> openSearchPage());
        menuPanel.addView(menuSearchButton, matchWrap());
        LinearLayout.LayoutParams menuParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        menuParams.topMargin = dp(8);
        root.addView(menuPanel, menuParams);

        changeLogList = new LinearLayout(this);
        changeLogList.setOrientation(LinearLayout.VERTICAL);
        changeLogList.setPadding(dp(12), dp(10), dp(12), dp(10));
        changeLogList.setBackground(makePanelBackground(Color.WHITE, dp(16), 1, Color.rgb(228, 233, 241)));
        changeLogPanel = new ScrollView(this);
        changeLogPanel.setVisibility(View.GONE);
        changeLogPanel.addView(changeLogList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams changeLogParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(210)
        );
        changeLogParams.topMargin = dp(8);
        root.addView(changeLogPanel, changeLogParams);
        renderChangeLog();

        logText = new TextView(this);
        logText.setTextSize(12);
        logText.setTextColor(Color.rgb(64, 72, 86));
        logText.setPadding(dp(12), dp(10), dp(12), dp(10));
        logText.setBackground(makePanelBackground(Color.WHITE, dp(16), 1, Color.rgb(228, 233, 241)));
        logPanel = new ScrollView(this);
        logPanel.setVisibility(View.GONE);
        logPanel.addView(logText, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams logParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(126)
        );
        logParams.topMargin = dp(8);
        root.addView(logPanel, logParams);

        messageList = new LinearLayout(this);
        messageList.setOrientation(LinearLayout.VERTICAL);
        messageList.setPadding(dp(10), dp(10), dp(10), dp(10));

        scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.setBackground(makePanelBackground(Color.rgb(239, 244, 248), dp(18), 1, Color.rgb(226, 232, 240)));
        scrollView.addView(messageList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams messageParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        );
        messageParams.topMargin = dp(4);
        root.addView(scrollView, messageParams);

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.VERTICAL);
        composer.setPadding(dp(10), dp(10), dp(10), dp(10));
        composer.setBackground(makePanelBackground(Color.WHITE, dp(20), 1, Color.rgb(226, 232, 240)));
        LinearLayout.LayoutParams composerParams = matchWrap();
        composerParams.topMargin = dp(10);

        selectedImagePanel = new LinearLayout(this);
        selectedImagePanel.setOrientation(LinearLayout.HORIZONTAL);
        selectedImagePanel.setGravity(Gravity.CENTER_VERTICAL);
        selectedImagePanel.setPadding(0, 0, 0, dp(8));
        selectedImagePanel.setVisibility(View.GONE);
        selectedImagePreview = new ImageView(this);
        selectedImagePreview.setVisibility(View.GONE);
        selectedImagePreview.setScaleType(ImageView.ScaleType.CENTER_CROP);
        selectedImagePanel.addView(selectedImagePreview, new LinearLayout.LayoutParams(dp(52), dp(52)));

        selectedImageLabel = new TextView(this);
        selectedImageLabel.setVisibility(View.GONE);
        selectedImageLabel.setTextColor(Color.rgb(62, 69, 82));
        selectedImageLabel.setTextSize(13);
        selectedImageLabel.setPadding(dp(10), 0, dp(10), 0);
        selectedImagePanel.addView(selectedImageLabel, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        clearImageButton = makeActionChip("移除", Color.rgb(255, 240, 235), Color.rgb(166, 63, 40));
        clearImageButton.setVisibility(View.GONE);
        clearImageButton.setOnClickListener(view -> clearSelectedImage());
        selectedImagePanel.addView(clearImageButton, new LinearLayout.LayoutParams(dp(66), dp(40)));
        composer.addView(selectedImagePanel, matchWrap());

        input = new EditText(this);
        input.setHint("给嫦娥发消息...");
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(4);
        input.setTextSize(16);
        input.setImeOptions(EditorInfo.IME_ACTION_SEND);
        input.setTextColor(Color.rgb(27, 34, 45));
        input.setHintTextColor(Color.rgb(142, 151, 166));
        input.setPadding(dp(12), dp(10), dp(12), dp(10));
        input.setBackground(makePanelBackground(Color.rgb(247, 249, 252), dp(16), 1, Color.rgb(226, 232, 240)));
        composer.addView(input, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        deliveryStatusBar = new TextView(this);
        deliveryStatusBar.setText("状态：就绪");
        deliveryStatusBar.setTextSize(12);
        deliveryStatusBar.setTypeface(Typeface.DEFAULT_BOLD);
        deliveryStatusBar.setTextColor(Color.rgb(91, 102, 118));
        deliveryStatusBar.setGravity(Gravity.CENTER_VERTICAL);
        deliveryStatusBar.setIncludeFontPadding(false);
        deliveryStatusBar.setSingleLine(false);
        deliveryStatusBar.setPadding(dp(10), 0, dp(10), 0);
        deliveryStatusBar.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(13), 1, Color.rgb(226, 232, 240)));
        LinearLayout.LayoutParams deliveryParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(34)
        );
        deliveryParams.topMargin = dp(8);
        composer.addView(deliveryStatusBar, deliveryParams);

        composerOptionsPanel = new LinearLayout(this);
        composerOptionsPanel.setOrientation(LinearLayout.VERTICAL);
        composerOptionsPanel.setPadding(dp(10), dp(8), dp(10), dp(10));
        composerOptionsPanel.setBackground(makePanelBackground(Color.rgb(247, 249, 252), dp(16), 1, Color.rgb(226, 232, 240)));
        composerOptionsPanel.setVisibility(View.GONE);

        LinearLayout targetRow = new LinearLayout(this);
        targetRow.setOrientation(LinearLayout.HORIZONTAL);
        targetRow.setGravity(Gravity.CENTER_VERTICAL);
        targetRow.setPadding(0, 0, 0, 0);

        hermesTargetButton = makeActionChip("Hermes 日常", Color.TRANSPARENT, Color.rgb(58, 70, 88));
        hermesTargetButton.setOnClickListener(view -> setChatTarget(TARGET_HERMES, true));
        targetRow.addView(hermesTargetButton, weightedHeight(1f, dp(42)));

        codexTargetButton = makeActionChip("Codex 专业", Color.TRANSPARENT, Color.rgb(58, 70, 88));
        codexTargetButton.setOnClickListener(view -> setChatTarget(TARGET_CODEX, true));
        LinearLayout.LayoutParams codexTargetParams = weightedHeight(1f, dp(42));
        codexTargetParams.leftMargin = dp(8);
        targetRow.addView(codexTargetButton, codexTargetParams);

        composerOptionsPanel.addView(targetRow);

        LinearLayout codexSessionRow = new LinearLayout(this);
        codexSessionRow.setOrientation(LinearLayout.HORIZONTAL);
        codexSessionRow.setGravity(Gravity.CENTER_VERTICAL);
        codexSessionRow.setPadding(0, dp(8), 0, 0);

        codexSessionLabel = new TextView(this);
        codexSessionLabel.setTextSize(12);
        codexSessionLabel.setTypeface(Typeface.DEFAULT_BOLD);
        codexSessionLabel.setTextColor(Color.rgb(91, 102, 118));
        codexSessionLabel.setGravity(Gravity.CENTER_VERTICAL);
        codexSessionLabel.setIncludeFontPadding(false);
        codexSessionLabel.setSingleLine(false);
        codexSessionLabel.setPadding(dp(10), 0, dp(10), 0);
        codexSessionLabel.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(13), 1, Color.rgb(226, 232, 240)));
        codexSessionRow.addView(codexSessionLabel, new LinearLayout.LayoutParams(0, dp(34), 1f));

        clearCodexSessionButton = makeActionChip("清除", Color.rgb(241, 242, 245), Color.rgb(91, 102, 118));
        clearCodexSessionButton.setTextSize(12);
        clearCodexSessionButton.setOnClickListener(view -> clearSelectedCodexSession(true));
        LinearLayout.LayoutParams clearSessionParams = new LinearLayout.LayoutParams(dp(62), dp(34));
        clearSessionParams.leftMargin = dp(8);
        codexSessionRow.addView(clearCodexSessionButton, clearSessionParams);

        composerOptionsPanel.addView(codexSessionRow);

        LinearLayout optionActions = new LinearLayout(this);
        optionActions.setOrientation(LinearLayout.HORIZONTAL);
        optionActions.setGravity(Gravity.CENTER_VERTICAL);
        optionActions.setPadding(0, dp(8), 0, 0);

        imageButton = makeActionChip("图片", Color.rgb(236, 243, 249), Color.rgb(38, 83, 111));
        imageButton.setOnClickListener(view -> pickImage());
        optionActions.addView(imageButton, weightedHeight(1f, dp(42)));

        healthButton = makeActionChip("连接", Color.rgb(239, 246, 239), Color.rgb(50, 114, 62));
        healthButton.setOnClickListener(view -> checkHealth());
        LinearLayout.LayoutParams healthParams = weightedHeight(1f, dp(42));
        healthParams.leftMargin = dp(8);
        optionActions.addView(healthButton, healthParams);

        composerOptionsPanel.addView(optionActions);
        LinearLayout.LayoutParams optionsPanelParams = matchWrap();
        optionsPanelParams.topMargin = dp(8);
        composer.addView(composerOptionsPanel, optionsPanelParams);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        actions.setPadding(0, dp(8), 0, 0);

        composerOptionsButton = makeActionChip("选项 ▼", Color.rgb(244, 247, 252), Color.rgb(62, 75, 96));
        composerOptionsButton.setOnClickListener(view -> toggleComposerOptionsPanel());
        actions.addView(composerOptionsButton, weightedHeight(1f, dp(44)));

        sendButton = makeActionChip("发送", Color.rgb(31, 111, 235), Color.WHITE);
        sendButton.setOnClickListener(view -> sendMessage());
        LinearLayout.LayoutParams sendParams = weightedHeight(1f, dp(44));
        sendParams.leftMargin = dp(8);
        actions.addView(sendButton, sendParams);

        composer.addView(actions);
        updateChatTargetButtons();
        updateComposerOptionsButton();
        root.addView(composer, composerParams);

        bottomTabBar = buildBottomTabBar();
        screenRoot.addView(bottomTabBar, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(58)
        ));
        updateBottomTabs();
        setContentView(screenRoot);
    }

    private LinearLayout buildSessionChatView() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(12), dp(12), dp(10));
        root.setBackgroundColor(Color.rgb(246, 247, 251));

        LinearLayout headerCard = new LinearLayout(this);
        headerCard.setOrientation(LinearLayout.VERTICAL);
        headerCard.setPadding(dp(14), dp(12), dp(14), dp(12));
        headerCard.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(228, 233, 241)));
        root.addView(headerCard, matchWrap());

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);

        TextView backButton = makeActionChip("返回", Color.rgb(236, 243, 249), Color.rgb(38, 83, 111));
        backButton.setOnClickListener(view -> showDashboard());
        header.addView(backButton, new LinearLayout.LayoutParams(dp(62), dp(42)));

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);
        titleBlock.setPadding(dp(10), 0, dp(8), 0);

        sessionTitle = new TextView(this);
        sessionTitle.setText("Codex Session");
        sessionTitle.setTextSize(21);
        sessionTitle.setTypeface(Typeface.DEFAULT_BOLD);
        sessionTitle.setTextColor(Color.rgb(26, 32, 43));
        titleBlock.addView(sessionTitle);

        sessionSubtitle = new TextView(this);
        sessionSubtitle.setText("未选择会话");
        sessionSubtitle.setTextSize(12);
        sessionSubtitle.setTextColor(Color.rgb(91, 101, 116));
        sessionSubtitle.setSingleLine(false);
        titleBlock.addView(sessionSubtitle);
        header.addView(titleBlock, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        sessionRenameButton = makeActionChip("改名", Color.rgb(231, 241, 255), Color.rgb(31, 96, 164));
        sessionRenameButton.setTextSize(12);
        sessionRenameButton.setOnClickListener(view -> showRenameCurrentSessionDialog());
        header.addView(sessionRenameButton, new LinearLayout.LayoutParams(dp(58), dp(34)));
        headerCard.addView(header, matchWrap());

        sessionMessageList = new LinearLayout(this);
        sessionMessageList.setOrientation(LinearLayout.VERTICAL);
        sessionMessageList.setPadding(dp(10), dp(10), dp(10), dp(10));

        sessionScrollView = new ScrollView(this);
        sessionScrollView.setFillViewport(true);
        sessionScrollView.setBackground(makePanelBackground(Color.rgb(240, 244, 250), dp(18), 1, Color.rgb(226, 232, 240)));
        sessionScrollView.addView(sessionMessageList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams messageParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        );
        messageParams.topMargin = dp(10);
        root.addView(sessionScrollView, messageParams);

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.VERTICAL);
        composer.setPadding(dp(10), dp(10), dp(10), dp(10));
        composer.setBackground(makePanelBackground(Color.WHITE, dp(20), 1, Color.rgb(226, 232, 240)));
        LinearLayout.LayoutParams composerParams = matchWrap();
        composerParams.topMargin = dp(10);

        sessionInput = new EditText(this);
        sessionInput.setHint("发给当前 Codex session...");
        sessionInput.setSingleLine(false);
        sessionInput.setMinLines(2);
        sessionInput.setMaxLines(4);
        sessionInput.setTextSize(16);
        sessionInput.setImeOptions(EditorInfo.IME_ACTION_SEND);
        sessionInput.setTextColor(Color.rgb(27, 34, 45));
        sessionInput.setHintTextColor(Color.rgb(142, 151, 166));
        sessionInput.setPadding(dp(12), dp(10), dp(12), dp(10));
        sessionInput.setBackground(makePanelBackground(Color.rgb(247, 249, 252), dp(16), 1, Color.rgb(226, 232, 240)));
        composer.addView(sessionInput, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        sessionDeliveryStatusBar = new TextView(this);
        sessionDeliveryStatusBar.setText("状态：就绪");
        sessionDeliveryStatusBar.setTextSize(12);
        sessionDeliveryStatusBar.setTypeface(Typeface.DEFAULT_BOLD);
        sessionDeliveryStatusBar.setTextColor(Color.rgb(91, 102, 118));
        sessionDeliveryStatusBar.setGravity(Gravity.CENTER_VERTICAL);
        sessionDeliveryStatusBar.setIncludeFontPadding(false);
        sessionDeliveryStatusBar.setSingleLine(false);
        sessionDeliveryStatusBar.setPadding(dp(10), 0, dp(10), 0);
        sessionDeliveryStatusBar.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(13), 1, Color.rgb(226, 232, 240)));
        LinearLayout.LayoutParams deliveryParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(34)
        );
        deliveryParams.topMargin = dp(8);
        composer.addView(sessionDeliveryStatusBar, deliveryParams);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        actions.setPadding(0, dp(8), 0, 0);

        sessionClearButton = makeActionChip("同步", Color.rgb(241, 242, 245), Color.rgb(91, 102, 118));
        sessionClearButton.setOnClickListener(view -> reloadCurrentSessionChat());
        actions.addView(sessionClearButton, weightedHeight(1f, dp(44)));

        sessionSendButton = makeActionChip("发送", Color.rgb(31, 111, 235), Color.WHITE);
        sessionSendButton.setOnClickListener(view -> sendSessionMessage());
        LinearLayout.LayoutParams sendParams = weightedHeight(1f, dp(44));
        sendParams.leftMargin = dp(8);
        actions.addView(sessionSendButton, sendParams);

        composer.addView(actions);
        root.addView(composer, composerParams);
        return root;
    }

    private LinearLayout buildBottomTabBar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(10), dp(6), dp(10), dp(8));
        bar.setBackground(makePanelBackground(Color.WHITE, 0, 1, Color.rgb(224, 231, 240)));

        hermesTabButton = makeBottomTab("Hermes", TAB_HERMES);
        bar.addView(hermesTabButton, weightedHeight(1f, dp(44)));

        codexTabButton = makeBottomTab("Codex", TAB_CODEX);
        LinearLayout.LayoutParams codexParams = weightedHeight(1f, dp(44));
        codexParams.leftMargin = dp(8);
        bar.addView(codexTabButton, codexParams);

        planTabButton = makeBottomTab("计划", TAB_PLAN);
        LinearLayout.LayoutParams planParams = weightedHeight(1f, dp(44));
        planParams.leftMargin = dp(8);
        bar.addView(planTabButton, planParams);
        return bar;
    }

    private TextView makeBottomTab(String label, String tab) {
        TextView button = makeActionChip(label, Color.rgb(244, 247, 252), Color.rgb(62, 75, 96));
        button.setTextSize(13);
        button.setOnClickListener(view -> {
            if (TAB_CODEX.equals(tab)) {
                showDashboard();
            } else if (TAB_PLAN.equals(tab)) {
                showPlan();
            } else {
                showChat();
            }
        });
        return button;
    }

    private LinearLayout buildPlanView() {
        LinearLayout plan = new LinearLayout(this);
        plan.setOrientation(LinearLayout.VERTICAL);
        plan.setPadding(dp(8), dp(8), dp(8), dp(8));
        plan.setBackgroundColor(Color.rgb(246, 247, 251));

        LinearLayout headerCard = new LinearLayout(this);
        headerCard.setOrientation(LinearLayout.VERTICAL);
        headerCard.setPadding(dp(12), dp(10), dp(12), dp(10));
        headerCard.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(228, 233, 241)));
        plan.addView(headerCard, matchWrap());

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);

        TextView title = new TextView(this);
        title.setText("计划视图");
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(26, 32, 43));
        titleBlock.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("CEO 分解 · Agent 异步汇报");
        subtitle.setTextSize(12);
        subtitle.setTextColor(Color.rgb(91, 101, 116));
        titleBlock.addView(subtitle);
        top.addView(titleBlock, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView refreshButton = makeActionChip("刷新", Color.rgb(239, 246, 239), Color.rgb(50, 114, 62));
        refreshButton.setTextSize(12);
        refreshButton.setOnClickListener(view -> pollPlanView());
        top.addView(refreshButton, new LinearLayout.LayoutParams(dp(64), dp(38)));
        headerCard.addView(top, matchWrap());

        LinearLayout stats = new LinearLayout(this);
        stats.setOrientation(LinearLayout.HORIZONTAL);
        stats.setPadding(0, dp(8), 0, 0);
        planSummary = makeDashboardStat("读取中", "项目");
        stats.addView(planSummary, weightedHeight(1f, dp(38)));
        planUpdated = makeDashboardStat("等待刷新", "更新时间");
        LinearLayout.LayoutParams updatedParams = weightedHeight(1f, dp(38));
        updatedParams.leftMargin = dp(8);
        stats.addView(planUpdated, updatedParams);
        headerCard.addView(stats, matchWrap());

        planProjectList = new LinearLayout(this);
        planProjectList.setOrientation(LinearLayout.VERTICAL);
        planProjectList.setPadding(dp(6), dp(6), dp(6), dp(6));
        planProjectList.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(226, 232, 240)));

        ScrollView projectScroll = new ScrollView(this);
        projectScroll.setFillViewport(true);
        projectScroll.addView(planProjectList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams listParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        );
        listParams.topMargin = dp(8);
        plan.addView(projectScroll, listParams);
        renderPlanLoading();
        return plan;
    }

    private LinearLayout buildDashboardView() {
        LinearLayout dashboard = new LinearLayout(this);
        dashboard.setOrientation(LinearLayout.VERTICAL);
        dashboard.setPadding(dp(8), dp(8), dp(8), dp(8));
        dashboard.setBackgroundColor(Color.rgb(246, 247, 251));

        LinearLayout headerCard = new LinearLayout(this);
        headerCard.setOrientation(LinearLayout.VERTICAL);
        headerCard.setPadding(dp(12), dp(10), dp(12), dp(10));
        headerCard.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(228, 233, 241)));
        dashboard.addView(headerCard, matchWrap());

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);

        TextView title = new TextView(this);
        title.setText("Codex");
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(26, 32, 43));
        titleBlock.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("会话列表 · 点击进入独立 session");
        subtitle.setTextSize(12);
        subtitle.setTextColor(Color.rgb(91, 101, 116));
        titleBlock.addView(subtitle);
        top.addView(titleBlock, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView refreshButton = makeActionChip("刷新", Color.rgb(239, 246, 239), Color.rgb(50, 114, 62));
        refreshButton.setTextSize(12);
        refreshButton.setOnClickListener(view -> pollCodexDashboard());
        LinearLayout.LayoutParams refreshParams = new LinearLayout.LayoutParams(dp(58), dp(38));
        refreshParams.rightMargin = dp(8);
        top.addView(refreshButton, refreshParams);

        dashboardCreateButton = makeActionChip("新建", Color.rgb(231, 241, 255), Color.rgb(31, 96, 164));
        dashboardCreateButton.setTextSize(12);
        dashboardCreateButton.setOnClickListener(view -> showCreateCodexSessionDialog());
        LinearLayout.LayoutParams createParams = new LinearLayout.LayoutParams(dp(58), dp(38));
        createParams.rightMargin = dp(8);
        top.addView(dashboardCreateButton, createParams);

        headerCard.addView(top, matchWrap());

        LinearLayout stats = new LinearLayout(this);
        stats.setOrientation(LinearLayout.HORIZONTAL);
        stats.setPadding(0, dp(8), 0, 0);
        dashboardSummary = makeDashboardStat("读取中", "会话");
        stats.addView(dashboardSummary, weightedHeight(1f, dp(38)));
        dashboardUpdated = makeDashboardStat("等待刷新", "更新时间");
        LinearLayout.LayoutParams updatedParams = weightedHeight(1f, dp(38));
        updatedParams.leftMargin = dp(8);
        stats.addView(dashboardUpdated, updatedParams);
        headerCard.addView(stats, matchWrap());

        dashboardSessionList = new LinearLayout(this);
        dashboardSessionList.setOrientation(LinearLayout.VERTICAL);
        dashboardSessionList.setPadding(dp(6), dp(6), dp(6), dp(6));
        dashboardSessionList.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(226, 232, 240)));

        ScrollView sessionScroll = new ScrollView(this);
        sessionScroll.setFillViewport(true);
        sessionScroll.addView(dashboardSessionList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams listParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        );
        listParams.topMargin = dp(8);
        dashboard.addView(sessionScroll, listParams);
        renderDashboardLoading();
        return dashboard;
    }

    private TextView makeDashboardStat(String primary, String secondary) {
        TextView stat = new TextView(this);
        stat.setText(primary + "\n" + secondary);
        stat.setTextSize(12);
        stat.setTypeface(Typeface.DEFAULT_BOLD);
        stat.setTextColor(Color.rgb(34, 45, 62));
        stat.setGravity(Gravity.CENTER);
        stat.setIncludeFontPadding(false);
        stat.setBackground(makePanelBackground(Color.rgb(246, 248, 252), dp(16), 1, Color.rgb(229, 234, 242)));
        return stat;
    }

    private void showDashboard() {
        showTopLevelTab(TAB_CODEX);
    }

    private void showChat() {
        showTopLevelTab(TAB_HERMES);
    }

    private void showPlan() {
        showTopLevelTab(TAB_PLAN);
    }

    private void showTopLevelTab(String tab) {
        boolean showCodex = TAB_CODEX.equals(tab);
        boolean showPlan = TAB_PLAN.equals(tab);
        dashboardVisible = showCodex;
        planVisible = showPlan;
        sessionChatVisible = false;
        stopSessionChatPolling();
        if (dashboardView != null) {
            dashboardView.setVisibility(showCodex ? View.VISIBLE : View.GONE);
        }
        if (planView != null) {
            planView.setVisibility(showPlan ? View.VISIBLE : View.GONE);
        }
        if (sessionChatView != null) {
            sessionChatView.setVisibility(View.GONE);
        }
        if (chatView != null) {
            chatView.setVisibility(!showCodex && !showPlan ? View.VISIBLE : View.GONE);
        }
        if (bottomTabBar != null) {
            bottomTabBar.setVisibility(View.VISIBLE);
        }
        if (showCodex) {
            startDashboardPolling();
            pollCodexDashboard();
        } else {
            stopDashboardPolling();
        }
        if (showPlan) {
            startPlanPolling();
            pollPlanView();
        } else {
            stopPlanPolling();
        }
        updateBottomTabs();
    }

    private void showSessionChat() {
        dashboardVisible = false;
        planVisible = false;
        sessionChatVisible = true;
        if (dashboardView != null) {
            dashboardView.setVisibility(View.GONE);
        }
        if (planView != null) {
            planView.setVisibility(View.GONE);
        }
        if (chatView != null) {
            chatView.setVisibility(View.GONE);
        }
        if (sessionChatView != null) {
            sessionChatView.setVisibility(View.VISIBLE);
        }
        if (bottomTabBar != null) {
            bottomTabBar.setVisibility(View.GONE);
        }
        stopDashboardPolling();
        stopPlanPolling();
        updateSessionHeader();
        renderCurrentSessionHistory();
        startSessionChatPolling();
        syncCurrentSessionMessages(true);
    }

    private void startDashboardPolling() {
        dashboardHandler.removeCallbacks(dashboardPollRunnable);
        dashboardHandler.postDelayed(dashboardPollRunnable, DASHBOARD_POLL_INTERVAL_MS);
    }

    private void stopDashboardPolling() {
        dashboardHandler.removeCallbacks(dashboardPollRunnable);
    }

    private void startSessionChatPolling() {
        sessionChatHandler.removeCallbacks(sessionChatPollRunnable);
        sessionChatHandler.postDelayed(sessionChatPollRunnable, SESSION_CHAT_POLL_INTERVAL_MS);
    }

    private void stopSessionChatPolling() {
        sessionChatHandler.removeCallbacks(sessionChatPollRunnable);
    }

    private void startPlanPolling() {
        planHandler.removeCallbacks(planPollRunnable);
        planHandler.postDelayed(planPollRunnable, PLAN_POLL_INTERVAL_MS);
    }

    private void stopPlanPolling() {
        planHandler.removeCallbacks(planPollRunnable);
    }

    private void updateBottomTabs() {
        styleBottomTab(hermesTabButton, !dashboardVisible && !planVisible && !sessionChatVisible);
        styleBottomTab(codexTabButton, dashboardVisible || sessionChatVisible);
        styleBottomTab(planTabButton, planVisible);
    }

    private void styleBottomTab(TextView button, boolean selected) {
        if (button == null) {
            return;
        }
        if (selected) {
            button.setTextColor(Color.WHITE);
            button.setBackground(makePanelBackground(Color.rgb(31, 111, 235), dp(15), 0, Color.TRANSPARENT));
        } else {
            button.setTextColor(Color.rgb(62, 75, 96));
            button.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(15), 1, Color.rgb(224, 231, 240)));
        }
    }

    private void renderDashboardLoading() {
        if (dashboardSessionList == null) {
            return;
        }
        dashboardSessionList.removeAllViews();
        TextView loading = new TextView(this);
        loading.setText("正在读取 Codex 会话状态...");
        loading.setTextSize(14);
        loading.setTextColor(Color.rgb(91, 101, 116));
        loading.setGravity(Gravity.CENTER);
        loading.setPadding(dp(12), dp(20), dp(12), dp(20));
        dashboardSessionList.addView(loading, matchWrap());
    }

    private void renderPlanLoading() {
        if (planProjectList == null) {
            return;
        }
        planProjectList.removeAllViews();
        TextView loading = new TextView(this);
        loading.setText("正在读取计划状态...");
        loading.setTextSize(14);
        loading.setTextColor(Color.rgb(91, 101, 116));
        loading.setGravity(Gravity.CENTER);
        loading.setPadding(dp(12), dp(20), dp(12), dp(20));
        planProjectList.addView(loading, matchWrap());
    }

    private void pollCodexDashboard() {
        if (dashboardSyncInFlight) {
            return;
        }
        dashboardSyncInFlight = true;
        executor.execute(() -> {
            try {
                JSONObject response = getJson(CODEX_DASHBOARD_URL);
                runOnUiThread(() -> renderCodexDashboard(response));
                dashboardErrorLogged = false;
            } catch (Exception exception) {
                if (!dashboardErrorLogged) {
                    dashboardErrorLogged = true;
                    appendLogFromWorker("Codex dashboard 同步失败：" + exception.getMessage());
                }
                runOnUiThread(() -> renderDashboardError(exception.getMessage()));
            } finally {
                dashboardSyncInFlight = false;
            }
        });
    }

    private void pollPlanView() {
        if (planSyncInFlight) {
            return;
        }
        planSyncInFlight = true;
        executor.execute(() -> {
            try {
                JSONObject response = getJson(PLAN_PROJECTS_URL);
                runOnUiThread(() -> renderPlanProjects(response));
                planErrorLogged = false;
            } catch (Exception exception) {
                if (!planErrorLogged) {
                    planErrorLogged = true;
                    appendLogFromWorker("计划视图同步失败：" + exception.getMessage());
                }
                runOnUiThread(() -> renderPlanError(exception.getMessage()));
            } finally {
                planSyncInFlight = false;
            }
        });
    }

    private void showCreateCodexSessionDialog() {
        EditText titleInput = makeSessionTitleInput("元宵新会话");
        titleInput.setText("元宵新会话");
        titleInput.selectAll();
        new AlertDialog.Builder(this)
                .setTitle("新建 Codex 会话")
                .setView(titleInput)
                .setNegativeButton("取消", null)
                .setPositiveButton("新建", (dialog, which) -> createCodexSession(titleInput.getText().toString()))
                .show();
    }

    private void showRenameCurrentSessionDialog() {
        if (selectedCodexSessionId.isEmpty()) {
            appendLog("先从 Dashboard 选择一个 Codex session。");
            return;
        }
        EditText titleInput = makeSessionTitleInput(compactSessionTitle(selectedCodexSessionTitle));
        titleInput.setText(compactSessionTitle(selectedCodexSessionTitle));
        titleInput.selectAll();
        new AlertDialog.Builder(this)
                .setTitle("重命名 Codex 会话")
                .setView(titleInput)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", (dialog, which) -> renameCurrentCodexSession(titleInput.getText().toString()))
                .show();
    }

    private EditText makeSessionTitleInput(String hint) {
        EditText titleInput = new EditText(this);
        titleInput.setSingleLine(true);
        titleInput.setHint(hint);
        titleInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        titleInput.setTextSize(16);
        titleInput.setPadding(dp(16), dp(10), dp(16), dp(10));
        return titleInput;
    }

    private String sanitizeSessionTitleInput(String rawTitle) {
        String title = rawTitle == null ? "" : rawTitle.trim().replaceAll("\\s+", " ");
        if (title.isEmpty()) {
            title = "元宵新会话";
        }
        if (title.length() > 80) {
            title = title.substring(0, 80).trim();
        }
        return title.isEmpty() ? "元宵新会话" : title;
    }

    private void createCodexSession(String rawTitle) {
        String title = sanitizeSessionTitleInput(rawTitle);
        setDashboardCreateBusy(true);
        appendLog("正在通过嫦娥新建 Codex session：" + title);
        executor.execute(() -> {
            try {
                JSONObject request = new JSONObject();
                request.put("title", title);
                JSONObject response = postJson(CODEX_SESSION_CREATE_URL, request);
                if (!"ok".equals(response.optString("status"))) {
                    throw new IllegalStateException(response.optString("error", "codex_session_create_failed"));
                }
                JSONObject session = response.optJSONObject("session");
                if (session == null) {
                    throw new IllegalStateException("missing_session");
                }
                runOnUiThread(() -> {
                    setDashboardCreateBusy(false);
                    openCodexSessionChat(session);
                    pollCodexDashboard();
                    appendLog("Codex session 已新建并进入：" + compactSessionTitle(selectedCodexSessionTitle));
                });
            } catch (Exception exception) {
                runOnUiThread(() -> setDashboardCreateBusy(false));
                appendLogFromWorker("新建 Codex session 失败：" + exception.getMessage());
            }
        });
    }

    private void renameCurrentCodexSession(String rawTitle) {
        String sessionId = selectedCodexSessionId;
        if (sessionId.isEmpty()) {
            appendLog("先从 Dashboard 选择一个 Codex session。");
            return;
        }
        String title = sanitizeSessionTitleInput(rawTitle);
        setSessionRenameBusy(true);
        appendLog("正在重命名 Codex session：" + title);
        executor.execute(() -> {
            try {
                JSONObject request = new JSONObject();
                request.put("session_id", sessionId);
                request.put("title", title);
                JSONObject response = postJson(CODEX_SESSION_RENAME_URL, request);
                if (!"ok".equals(response.optString("status"))) {
                    throw new IllegalStateException(response.optString("error", "codex_session_rename_failed"));
                }
                JSONObject session = response.optJSONObject("session");
                String remoteTitle = session == null ? title : session.optString("title", title).trim();
                runOnUiThread(() -> {
                    setSessionRenameBusy(false);
                    if (!sessionId.equals(selectedCodexSessionId)) {
                        return;
                    }
                    selectedCodexSessionTitle = remoteTitle.isEmpty() ? title : remoteTitle;
                    getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                            .edit()
                            .putString(KEY_CODEX_SESSION_TITLE, selectedCodexSessionTitle)
                            .apply();
                    updateSessionHeader();
                    pollCodexDashboard();
                    appendLog("Codex session 已重命名：" + compactSessionTitle(selectedCodexSessionTitle));
                });
            } catch (Exception exception) {
                runOnUiThread(() -> setSessionRenameBusy(false));
                appendLogFromWorker("重命名 Codex session 失败：" + exception.getMessage());
            }
        });
    }

    private void setDashboardCreateBusy(boolean busy) {
        if (dashboardCreateButton == null) {
            return;
        }
        dashboardCreateButton.setEnabled(!busy);
        dashboardCreateButton.setText(busy ? "等待" : "新建");
    }

    private void setSessionRenameBusy(boolean busy) {
        if (sessionRenameButton == null) {
            return;
        }
        boolean enabled = !busy && !selectedCodexSessionId.isEmpty() && !sessionSendInFlight;
        sessionRenameButton.setEnabled(enabled);
        sessionRenameButton.setText(busy ? "等待" : "改名");
    }

    private void syncCurrentSessionMessages(boolean initialLoad) {
        String sessionId = selectedCodexSessionId;
        if (sessionId.isEmpty() || sessionSyncInFlight) {
            return;
        }
        sessionSyncInFlight = true;
        if (initialLoad && !sessionSendInFlight) {
            setSessionDeliverySyncing();
        }
        executor.execute(() -> {
            try {
                JSONObject response = getJson(buildSessionMessagesUrl(sessionId, initialLoad));
                JSONArray messages = response.optJSONArray("messages");
                String remoteTitle = response.optString("title", "");
                runOnUiThread(() -> {
                    if (!sessionId.equals(selectedCodexSessionId)) {
                        return;
                    }
                    if (!remoteTitle.trim().isEmpty()) {
                        selectedCodexSessionTitle = remoteTitle.trim();
                        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                                .edit()
                                .putString(KEY_CODEX_SESSION_TITLE, selectedCodexSessionTitle)
                                .apply();
                        updateSessionHeader();
                    }
                    SessionMergeResult result = mergeSessionMessagesFromJson(sessionId, messages);
                    if (result.needsFullRender || initialLoad) {
                        renderCurrentSessionHistory();
                    } else if (!result.appendedMessages.isEmpty()) {
                        appendSessionRenderedMessages(result.appendedMessages);
                    }
                    if (!initialLoad && result.hasNewAssistantMessage) {
                        showIncomingNotification("Codex session 有新消息", result.newestAssistantText, false);
                    }
                    if (!sessionSendInFlight) {
                        setSessionDeliverySynced();
                    }
                });
                sessionSyncErrorLogged = false;
            } catch (Exception exception) {
                if (!sessionSyncErrorLogged) {
                    sessionSyncErrorLogged = true;
                    appendLogFromWorker("Codex session 历史同步失败：" + exception.getMessage());
                }
                if (initialLoad && !sessionSendInFlight) {
                    runOnUiThread(() -> setSessionDeliveryFailed());
                }
            } finally {
                sessionSyncInFlight = false;
            }
        });
    }

    private String buildSessionMessagesUrl(String sessionId, boolean initialLoad) throws Exception {
        String targetUrl = CODEX_SESSION_MESSAGES_URL
                + "?session_id=" + URLEncoder.encode(sessionId, "UTF-8")
                + "&limit=" + (initialLoad ? "200" : "50");
        long cursor = currentSessionRemoteCursor(sessionId);
        if (!initialLoad && cursor > 0) {
            targetUrl += "&after_order=" + cursor;
        }
        return targetUrl;
    }

    private void renderDashboardError(String message) {
        dashboardSummary.setText("不可用\nCodex");
        dashboardUpdated.setText(stamp() + "\n更新时间");
        dashboardSessionList.removeAllViews();
        TextView error = new TextView(this);
        error.setText("暂时无法读取会话状态：" + message);
        error.setTextSize(14);
        error.setTextColor(Color.rgb(166, 63, 40));
        error.setPadding(dp(12), dp(16), dp(12), dp(16));
        dashboardSessionList.addView(error, matchWrap());
    }

    private void renderPlanError(String message) {
        if (planSummary != null) {
            planSummary.setText("不可用\n计划");
        }
        if (planUpdated != null) {
            planUpdated.setText(stamp() + "\n更新时间");
        }
        if (planProjectList == null) {
            return;
        }
        planProjectList.removeAllViews();
        TextView error = new TextView(this);
        error.setText("暂时无法读取计划状态：" + message);
        error.setTextSize(14);
        error.setTextColor(Color.rgb(166, 63, 40));
        error.setPadding(dp(12), dp(16), dp(12), dp(16));
        planProjectList.addView(error, matchWrap());
    }

    private void renderCodexDashboard(JSONObject response) {
        lastDashboardResponse = response;
        JSONObject process = response.optJSONObject("process");
        JSONObject summary = response.optJSONObject("summary");
        int visible = summary == null ? 0 : summary.optInt("visible_sessions", 0);
        int active = summary == null ? 0 : summary.optInt("active_sessions", 0);
        boolean appRunning = process != null && process.optBoolean("app_running", false);
        dashboardSummary.setText((appRunning ? "运行中" : "未运行") + " · " + active + "/" + visible + "\n会话");
        dashboardUpdated.setText(stamp() + "\n更新时间");

        dashboardSessionList.removeAllViews();
        JSONArray sessions = response.optJSONArray("sessions");
        if (sessions == null || sessions.length() == 0) {
            TextView empty = new TextView(this);
            empty.setText("没有读到 Codex 会话。");
            empty.setTextSize(14);
            empty.setTextColor(Color.rgb(91, 101, 116));
            empty.setPadding(dp(12), dp(20), dp(12), dp(20));
            dashboardSessionList.addView(empty, matchWrap());
            return;
        }
        List<JSONObject> activeSessions = new ArrayList<>();
        List<JSONObject> recentSessions = new ArrayList<>();
        List<JSONObject> idleSessions = new ArrayList<>();
        List<JSONObject> archivedSessions = new ArrayList<>();
        for (int i = 0; i < sessions.length(); i++) {
            JSONObject session = sessions.optJSONObject(i);
            if (session == null) {
                continue;
            }
            String status = normalizedSessionStatus(session);
            if ("active".equals(status)) {
                activeSessions.add(session);
            } else if ("recent".equals(status)) {
                recentSessions.add(session);
            } else if ("archived".equals(status)) {
                archivedSessions.add(session);
            } else {
                idleSessions.add(session);
            }
        }
        addDashboardSection("active", activeSessions);
        addDashboardSection("recent", recentSessions);
        addDashboardSection("idle", idleSessions);
        addDashboardSection("archived", archivedSessions);
    }

    private void renderPlanProjects(JSONObject response) {
        JSONObject summary = response.optJSONObject("summary");
        int projectCount = summary == null ? 0 : summary.optInt("project_count", 0);
        int agentCount = summary == null ? 0 : summary.optInt("agent_count", 0);
        int activeAgents = summary == null ? 0 : summary.optInt("active_agents", 0);
        int blockedAgents = summary == null ? 0 : summary.optInt("blocked_agents", 0);
        if (planSummary != null) {
            planSummary.setText(projectCount + " 项 · " + activeAgents + "/" + agentCount + "\nAgent");
        }
        if (planUpdated != null) {
            String updatedAt = response.optString("updated_at", response.optString("time", ""));
            String label = updatedAt.trim().isEmpty() ? stamp() : formatDashboardTime(updatedAt);
            planUpdated.setText(label + (blockedAgents > 0 ? " · 阻塞 " + blockedAgents : "") + "\n更新时间");
        }
        if (planProjectList == null) {
            return;
        }
        planProjectList.removeAllViews();
        JSONArray projects = response.optJSONArray("projects");
        if (projects == null || projects.length() == 0) {
            TextView empty = new TextView(this);
            empty.setText("暂无计划项目。");
            empty.setTextSize(14);
            empty.setTextColor(Color.rgb(91, 101, 116));
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(12), dp(28), dp(12), dp(28));
            planProjectList.addView(empty, matchWrap());
            return;
        }
        for (int i = 0; i < projects.length(); i++) {
            JSONObject project = projects.optJSONObject(i);
            if (project == null) {
                continue;
            }
            LinearLayout.LayoutParams params = sessionRowParams();
            planProjectList.addView(makePlanProjectCard(project), params);
        }
    }

    private LinearLayout makePlanProjectCard(JSONObject project) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(10), dp(9), dp(10), dp(9));
        card.setBackground(makePanelBackground(Color.rgb(247, 249, 252), dp(14), 1, Color.rgb(229, 234, 242)));

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText(firstNonEmpty(project.optString("title", ""), project.optString("name", ""), "未命名项目"));
        title.setTextSize(15);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(29, 36, 48));
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        top.addView(title, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView status = makePlanStatusBadge(project.optString("status", "queued"));
        LinearLayout.LayoutParams statusParams = new LinearLayout.LayoutParams(dp(62), dp(28));
        statusParams.leftMargin = dp(8);
        top.addView(status, statusParams);
        card.addView(top, matchWrap());

        LinearLayout progressRow = new LinearLayout(this);
        progressRow.setOrientation(LinearLayout.HORIZONTAL);
        progressRow.setGravity(Gravity.CENTER_VERTICAL);
        progressRow.setPadding(0, dp(7), 0, 0);
        progressRow.addView(makeProgressBar(progressFromJson(project)), new LinearLayout.LayoutParams(0, dp(8), 1f));
        TextView updated = new TextView(this);
        updated.setText(formatDashboardTime(project.optString("updated_at", "")));
        updated.setTextSize(11);
        updated.setTextColor(Color.rgb(112, 121, 137));
        updated.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams updatedParams = new LinearLayout.LayoutParams(dp(82), LinearLayout.LayoutParams.WRAP_CONTENT);
        updatedParams.leftMargin = dp(8);
        progressRow.addView(updated, updatedParams);
        card.addView(progressRow, matchWrap());

        JSONObject ceo = project.optJSONObject("ceo");
        if (ceo != null) {
            LinearLayout.LayoutParams ceoParams = matchWrap();
            ceoParams.topMargin = dp(8);
            card.addView(makePlanPersonRow("CEO", ceo), ceoParams);
        }

        JSONArray agents = project.optJSONArray("agents");
        if (agents != null) {
            int maxRows = Math.min(agents.length(), 6);
            for (int i = 0; i < maxRows; i++) {
                JSONObject agent = agents.optJSONObject(i);
                if (agent == null) {
                    continue;
                }
                LinearLayout.LayoutParams rowParams = matchWrap();
                rowParams.topMargin = dp(6);
                card.addView(makePlanPersonRow("Agent", agent), rowParams);
            }
            if (agents.length() > maxRows) {
                TextView more = new TextView(this);
                more.setText("还有 " + (agents.length() - maxRows) + " 个 Agent");
                more.setTextSize(12);
                more.setTextColor(Color.rgb(104, 112, 126));
                more.setPadding(dp(4), dp(6), dp(4), 0);
                card.addView(more, matchWrap());
            }
        }

        String report = compactOneLine(project.optString("last_report", ""), 96);
        if (!report.isEmpty()) {
            TextView reportView = new TextView(this);
            reportView.setText(report);
            reportView.setTextSize(12);
            reportView.setTextColor(Color.rgb(91, 101, 116));
            reportView.setPadding(dp(4), dp(7), dp(4), 0);
            reportView.setSingleLine(true);
            reportView.setEllipsize(TextUtils.TruncateAt.END);
            card.addView(reportView, matchWrap());
        }
        return card;
    }

    private LinearLayout makePlanPersonRow(String prefix, JSONObject person) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(8), dp(6), dp(8), dp(6));
        row.setBackground(makePanelBackground(Color.WHITE, dp(12), 1, Color.rgb(230, 235, 243)));

        LinearLayout textBlock = new LinearLayout(this);
        textBlock.setOrientation(LinearLayout.VERTICAL);

        TextView name = new TextView(this);
        name.setText(prefix + " · " + planPersonName(person));
        name.setTextSize(13);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        name.setTextColor(Color.rgb(34, 45, 62));
        name.setSingleLine(true);
        name.setEllipsize(TextUtils.TruncateAt.END);
        textBlock.addView(name);

        String report = compactOneLine(person.optString("last_report", person.optString("current_task", "")), 72);
        TextView detail = new TextView(this);
        detail.setText(report.isEmpty() ? planStatusLabel(person.optString("status", "queued")) : report);
        detail.setTextSize(11);
        detail.setTextColor(Color.rgb(104, 112, 126));
        detail.setSingleLine(true);
        detail.setEllipsize(TextUtils.TruncateAt.END);
        textBlock.addView(detail);
        row.addView(textBlock, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView progress = makeBadge(progressFromJson(person) + "%", Color.rgb(236, 243, 249), Color.rgb(38, 83, 111));
        progress.setTextSize(11);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(dp(48), dp(26));
        progressParams.leftMargin = dp(8);
        row.addView(progress, progressParams);
        return row;
    }

    private TextView makePlanStatusBadge(String status) {
        String normalized = status == null ? "" : status.trim().toLowerCase(Locale.US);
        int bg = Color.rgb(241, 242, 245);
        int fg = Color.rgb(102, 111, 125);
        if ("running".equals(normalized) || "active".equals(normalized)) {
            bg = Color.rgb(232, 247, 240);
            fg = Color.rgb(20, 120, 82);
        } else if ("blocked".equals(normalized) || "failed".equals(normalized)) {
            bg = Color.rgb(255, 240, 235);
            fg = Color.rgb(166, 63, 40);
        } else if ("review".equals(normalized) || "waiting".equals(normalized)) {
            bg = Color.rgb(247, 241, 226);
            fg = Color.rgb(111, 78, 24);
        }
        TextView badge = makeBadge(planStatusLabel(normalized), bg, fg);
        badge.setTextSize(11);
        return badge;
    }

    private String planStatusLabel(String status) {
        String normalized = status == null ? "" : status.trim().toLowerCase(Locale.US);
        if ("running".equals(normalized) || "active".equals(normalized)) {
            return "进行";
        }
        if ("blocked".equals(normalized)) {
            return "阻塞";
        }
        if ("failed".equals(normalized)) {
            return "失败";
        }
        if ("done".equals(normalized) || "completed".equals(normalized)) {
            return "完成";
        }
        if ("review".equals(normalized)) {
            return "复核";
        }
        if ("waiting".equals(normalized)) {
            return "等待";
        }
        return "排队";
    }

    private String planPersonName(JSONObject person) {
        return firstNonEmpty(
                person.optString("name", ""),
                person.optString("title", ""),
                person.optString("role", ""),
                "未命名"
        );
    }

    private int progressFromJson(JSONObject item) {
        double raw = item.optDouble("progress", item.optDouble("progress_percent", 0));
        if (raw > 0 && raw <= 1) {
            raw *= 100;
        }
        return Math.max(0, Math.min(100, (int) Math.round(raw)));
    }

    private LinearLayout makeProgressBar(int progress) {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setWeightSum(100f);
        bar.setBackground(makePanelBackground(Color.rgb(228, 234, 242), dp(4), 0, Color.TRANSPARENT));
        if (progress > 0) {
            View fill = new View(this);
            fill.setBackground(makePanelBackground(Color.rgb(31, 111, 235), dp(4), 0, Color.TRANSPARENT));
            bar.addView(fill, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, progress));
        }
        if (progress < 100) {
            View rest = new View(this);
            bar.addView(rest, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, Math.max(1, 100 - progress)));
        }
        return bar;
    }

    private String normalizedSessionStatus(JSONObject session) {
        if (session.optBoolean("archived", false)) {
            return "archived";
        }
        String status = session.optString("status", "idle");
        if ("active".equals(status) || "recent".equals(status) || "archived".equals(status)) {
            return status;
        }
        return "idle";
    }

    private void addDashboardSection(String status, List<JSONObject> sessions) {
        if (sessions.isEmpty()) {
            return;
        }
        boolean expanded = isDashboardSectionExpanded(status);
        TextView header = makeDashboardSectionHeader(status, sessions.size(), expanded);
        header.setOnClickListener(view -> {
            toggleDashboardSection(status);
            if (lastDashboardResponse != null) {
                renderCodexDashboard(lastDashboardResponse);
            }
        });
        dashboardSessionList.addView(header, sectionHeaderParams());
        if (!expanded) {
            TextView folded = new TextView(this);
            folded.setText("已折叠 " + sessions.size() + " 个" + statusLabel(status) + "会话");
            folded.setTextSize(12);
            folded.setTextColor(Color.rgb(104, 112, 126));
            folded.setPadding(dp(10), dp(2), dp(10), dp(8));
            dashboardSessionList.addView(folded, matchWrap());
            return;
        }
        for (JSONObject session : sessions) {
            dashboardSessionList.addView(makeSessionRow(session), sessionRowParams());
        }
    }

    private TextView makeDashboardSectionHeader(String status, int count, boolean expanded) {
        int bg = Color.rgb(239, 246, 239);
        int fg = Color.rgb(50, 114, 62);
        if ("recent".equals(status)) {
            bg = Color.rgb(236, 243, 249);
            fg = Color.rgb(38, 83, 111);
        } else if ("idle".equals(status)) {
            bg = Color.rgb(247, 241, 226);
            fg = Color.rgb(111, 78, 24);
        } else if ("archived".equals(status)) {
            bg = Color.rgb(241, 242, 245);
            fg = Color.rgb(102, 111, 125);
        }
        TextView header = makeActionChip(statusLabel(status) + "  " + count + "  " + (expanded ? "▼" : "▶"), bg, fg);
        header.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        header.setPadding(dp(12), 0, dp(12), 0);
        return header;
    }

    private LinearLayout.LayoutParams sectionHeaderParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(34)
        );
        params.topMargin = dp(6);
        params.bottomMargin = dp(4);
        return params;
    }

    private boolean isDashboardSectionExpanded(String status) {
        if ("active".equals(status)) {
            return dashboardActiveExpanded;
        }
        if ("recent".equals(status)) {
            return dashboardRecentExpanded;
        }
        if ("archived".equals(status)) {
            return dashboardArchivedExpanded;
        }
        return dashboardIdleExpanded;
    }

    private void toggleDashboardSection(String status) {
        if ("active".equals(status)) {
            dashboardActiveExpanded = !dashboardActiveExpanded;
        } else if ("recent".equals(status)) {
            dashboardRecentExpanded = !dashboardRecentExpanded;
        } else if ("archived".equals(status)) {
            dashboardArchivedExpanded = !dashboardArchivedExpanded;
        } else {
            dashboardIdleExpanded = !dashboardIdleExpanded;
        }
    }

    private LinearLayout.LayoutParams sessionRowParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.bottomMargin = dp(5);
        return params;
    }

    private LinearLayout makeSessionRow(JSONObject session) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.VERTICAL);
        row.setPadding(dp(10), dp(8), dp(10), dp(8));
        row.setBackground(makePanelBackground(Color.rgb(247, 249, 252), dp(14), 1, Color.rgb(229, 234, 242)));
        row.setOnClickListener(view -> openCodexSessionChat(session));

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText(sessionDisplayName(session));
        title.setTextSize(15);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(29, 36, 48));
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        top.addView(title, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView updated = new TextView(this);
        updated.setText(formatDashboardTime(session.optString("updated_at", "")));
        updated.setTextSize(12);
        updated.setTextColor(Color.rgb(112, 121, 137));
        updated.setSingleLine(true);
        updated.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams updatedParams = new LinearLayout.LayoutParams(dp(82), LinearLayout.LayoutParams.WRAP_CONTENT);
        updatedParams.leftMargin = dp(8);
        top.addView(updated, updatedParams);
        row.addView(top, matchWrap());

        TextView preview = new TextView(this);
        preview.setText(sessionPreviewText(session));
        preview.setTextSize(13);
        preview.setTextColor(Color.rgb(91, 101, 116));
        preview.setSingleLine(true);
        preview.setEllipsize(TextUtils.TruncateAt.END);
        preview.setPadding(0, dp(4), 0, 0);
        row.addView(preview, matchWrap());
        return row;
    }

    private String sessionDisplayName(JSONObject session) {
        String nickname = session.optString("agent_nickname", "").trim();
        if (!nickname.isEmpty()) {
            return nickname;
        }
        String title = session.optString("title", "").trim();
        return title.isEmpty() ? "未命名会话" : title;
    }

    private String sessionPreviewText(JSONObject session) {
        String preview = firstNonEmpty(
                session.optString("last_message_preview", ""),
                session.optString("message_preview", ""),
                session.optString("preview", ""),
                session.optString("first_user_message", "")
        );
        if (preview.isEmpty()) {
            return "暂无最近消息";
        }
        return compactOneLine(preview, 88);
    }

    private String firstNonEmpty(String... values) {
        for (String value : values) {
            String cleaned = value == null ? "" : value.trim();
            if (!cleaned.isEmpty()) {
                return cleaned;
            }
        }
        return "";
    }

    private String compactOneLine(String value, int limit) {
        String cleaned = value == null ? "" : value.replaceAll("\\s+", " ").trim();
        if (cleaned.length() <= limit) {
            return cleaned;
        }
        return cleaned.substring(0, Math.max(1, limit - 1)).trim() + "…";
    }

    private String formatDashboardTime(String isoText) {
        String raw = isoText == null ? "" : isoText.trim();
        if (raw.isEmpty()) {
            return "刚刚";
        }
        String[] patterns = {
                "yyyy-MM-dd'T'HH:mm:ssXXX",
                "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
                "yyyy-MM-dd'T'HH:mm:ss'Z'"
        };
        for (String pattern : patterns) {
            try {
                SimpleDateFormat parser = new SimpleDateFormat(pattern, Locale.US);
                Date date = parser.parse(raw);
                if (date == null) {
                    continue;
                }
                Date now = new Date();
                String today = new SimpleDateFormat("yyyyMMdd", Locale.CHINA).format(now);
                String day = new SimpleDateFormat("yyyyMMdd", Locale.CHINA).format(date);
                if (today.equals(day)) {
                    return new SimpleDateFormat("HH:mm", Locale.CHINA).format(date);
                }
                String thisYear = new SimpleDateFormat("yyyy", Locale.CHINA).format(now);
                String year = new SimpleDateFormat("yyyy", Locale.CHINA).format(date);
                if (thisYear.equals(year)) {
                    return new SimpleDateFormat("MM/dd HH:mm", Locale.CHINA).format(date);
                }
                return new SimpleDateFormat("yy/MM/dd", Locale.CHINA).format(date);
            } catch (Exception ignored) {
            }
        }
        return compactOneLine(raw.replace("T", " "), 14);
    }

    private TextView makeStatusBadge(String status) {
        int bg = Color.rgb(239, 246, 239);
        int fg = Color.rgb(50, 114, 62);
        String label = statusLabel(status);
        if ("active".equals(status)) {
            bg = Color.rgb(232, 247, 240);
            fg = Color.rgb(20, 120, 82);
        } else if ("recent".equals(status)) {
            bg = Color.rgb(236, 243, 249);
            fg = Color.rgb(38, 83, 111);
        } else if ("archived".equals(status)) {
            bg = Color.rgb(241, 242, 245);
            fg = Color.rgb(102, 111, 125);
        }
        return makeBadge(label, bg, fg);
    }

    private String statusLabel(String status) {
        if ("active".equals(status)) {
            return "活跃";
        }
        if ("recent".equals(status)) {
            return "最近";
        }
        if ("archived".equals(status)) {
            return "归档";
        }
        return "空闲";
    }

    private String formatTokens(long tokens) {
        if (tokens >= 1_000_000) {
            return String.format(Locale.CHINA, "%.1fM tokens", tokens / 1_000_000.0);
        }
        if (tokens >= 1_000) {
            return String.format(Locale.CHINA, "%.1fK tokens", tokens / 1_000.0);
        }
        return tokens + " tokens";
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams weightedWrap(float weight) {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, weight);
    }

    private LinearLayout.LayoutParams weightedHeight(float weight, int height) {
        return new LinearLayout.LayoutParams(0, height, weight);
    }

    private TextView makeBadge(String text, int backgroundColor, int textColor) {
        TextView badge = new TextView(this);
        badge.setText(text);
        badge.setTextSize(13);
        badge.setTypeface(Typeface.DEFAULT_BOLD);
        badge.setTextColor(textColor);
        badge.setGravity(Gravity.CENTER);
        badge.setIncludeFontPadding(false);
        badge.setBackground(makePanelBackground(backgroundColor, dp(14), 0, Color.TRANSPARENT));
        return badge;
    }

    private TextView makeActionChip(String text, int backgroundColor, int textColor) {
        TextView chip = new TextView(this);
        chip.setText(text);
        chip.setTextSize(14);
        chip.setTypeface(Typeface.DEFAULT_BOLD);
        chip.setTextColor(textColor);
        chip.setGravity(Gravity.CENTER);
        chip.setMinHeight(dp(42));
        chip.setIncludeFontPadding(false);
        chip.setPadding(dp(10), 0, dp(10), 0);
        chip.setSingleLine(false);
        chip.setClickable(true);
        chip.setFocusable(true);
        chip.setBackground(makePanelBackground(backgroundColor, dp(15), 0, Color.TRANSPARENT));
        return chip;
    }

    private TextView makeTinyButton(String text) {
        TextView button = new TextView(this);
        button.setText(text);
        button.setTextSize(13);
        button.setTypeface(Typeface.DEFAULT_BOLD);
        button.setTextColor(Color.rgb(43, 72, 93));
        button.setGravity(Gravity.CENTER);
        button.setIncludeFontPadding(false);
        button.setClickable(true);
        button.setFocusable(true);
        button.setBackground(makePanelBackground(Color.rgb(238, 244, 248), dp(13), 0, Color.TRANSPARENT));
        return button;
    }

    private TextView makeCopyIconButton() {
        TextView button = makeTinyButton("⧉");
        button.setTextSize(16);
        button.setTypeface(Typeface.DEFAULT);
        button.setTextColor(Color.rgb(72, 84, 101));
        button.setContentDescription("复制本条聊天内容");
        button.setBackground(makePanelBackground(Color.rgb(247, 250, 253), dp(16), 1, Color.rgb(220, 228, 238)));
        return button;
    }

    private void addTinyButton(LinearLayout row, TextView button) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(dp(42), dp(44));
        params.leftMargin = dp(6);
        row.addView(button, params);
    }

    private GradientDrawable makePanelBackground(int color, int radius, int strokeWidth, int strokeColor) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radius);
        if (strokeWidth > 0) {
            drawable.setStroke(strokeWidth, strokeColor);
        }
        return drawable;
    }

    private void seedChangeLog() {
        releaseGroups.clear();
        ReleaseGroup v0 = new ReleaseGroup("v0 内测线");
        v0.entries.add(new ReleaseEntry("0.29", "底部新增 Hermes、Codex、计划三 Tab。"));
        v0.entries.add(new ReleaseEntry("0.29", "计划视图可读取异步 Agent 项目状态。"));
        v0.entries.add(new ReleaseEntry("0.29", "新增独立计划调度状态脚本。"));
        v0.entries.add(new ReleaseEntry("0.28", "Dashboard 和收件箱轮询避免叠请求。"));
        v0.entries.add(new ReleaseEntry("0.28", "bridge 结构化请求日志增加裁剪。"));
        v0.entries.add(new ReleaseEntry("0.27", "长 Codex session 等待时间提升到 15 分钟。"));
        v0.entries.add(new ReleaseEntry("0.27", "修复超大 session 易断开的链路超时。"));
        v0.entries.add(new ReleaseEntry("0.26", "Dashboard 可新建 Codex 会话。"));
        v0.entries.add(new ReleaseEntry("0.26", "session 页面可在元宵内重命名。"));
        v0.entries.add(new ReleaseEntry("0.25", "嫦娥主聊天历史会本地保留。"));
        v0.entries.add(new ReleaseEntry("0.25", "和嫦娥沟通使用稳定主会话标识。"));
        v0.entries.add(new ReleaseEntry("0.24", "Dashboard 智能体列表改为紧凑预览。"));
        v0.entries.add(new ReleaseEntry("0.24", "智能体行只展示名称、最近消息和时间。"));
        v0.entries.add(new ReleaseEntry("0.23", "session 新消息渲染改为增量追加。"));
        v0.entries.add(new ReleaseEntry("0.23", "日志面板限制保留最近记录降低内存压力。"));
        v0.entries.add(new ReleaseEntry("0.23", "Markdown 富文本解析增加小缓存。"));
        v0.entries.add(new ReleaseEntry("0.22", "session 历史轮询改为增量读取缺失消息。"));
        v0.entries.add(new ReleaseEntry("0.22", "Mac mini 日志读取增加缓存和追加读取。"));
        v0.entries.add(new ReleaseEntry("0.21", "指定 Codex session 会自动同步 Mac mini 历史。"));
        v0.entries.add(new ReleaseEntry("0.21", "session 页面新消息会保留并随轮询更新。"));
        v0.entries.add(new ReleaseEntry("0.20", "安装后应用名显示为中文元宵。"));
        v0.entries.add(new ReleaseEntry("0.19", "新增应用内新消息横幅提醒。"));
        v0.entries.add(new ReleaseEntry("0.19", "Markdown 表格列宽对齐更稳定。"));
        v0.entries.add(new ReleaseEntry("0.18", "主聊天底部选项改为可折叠面板。"));
        v0.entries.add(new ReleaseEntry("0.18", "默认只保留输入、状态、选项和发送。"));
        v0.entries.add(new ReleaseEntry("0.17", "具体 Codex session 使用独立聊天页面。"));
        v0.entries.add(new ReleaseEntry("0.17", "主聊天不再混入指定 session 消息。"));
        v0.entries.add(new ReleaseEntry("0.16", "Dashboard 每个 Codex 会话新增对话入口。"));
        v0.entries.add(new ReleaseEntry("0.16", "聊天可把消息发到指定 Codex session。"));
        v0.entries.add(new ReleaseEntry("0.15", "新增嫦娥已收到和已回复状态栏。"));
        v0.entries.add(new ReleaseEntry("0.14", "复制操作移到聊天气泡外右下角小图标。"));
        v0.entries.add(new ReleaseEntry("0.13", "聊天底部新增 Hermes 日常和 Codex 专业选择。"));
        v0.entries.add(new ReleaseEntry("0.13", "发送消息时按所选对象进入不同回复链路。"));
        v0.entries.add(new ReleaseEntry("0.12", "Dashboard 按会话状态分节展示。"));
        v0.entries.add(new ReleaseEntry("0.12", "归档会话在 Dashboard 默认折叠。"));
        v0.entries.add(new ReleaseEntry("0.11", "聊天内容支持 Markdown 富文本和表格。"));
        v0.entries.add(new ReleaseEntry("0.11", "链接、文件卡片和图片附件可点击查看。"));
        v0.entries.add(new ReleaseEntry("0.11", "每条聊天泡泡新增一键复制按钮。"));
        v0.entries.add(new ReleaseEntry("0.10", "新增 Codex 会话状态 Dashboard。"));
        v0.entries.add(new ReleaseEntry("0.10", "聊天页左上角改为返回 Dashboard。"));
        v0.entries.add(new ReleaseEntry("0.10", "嫦娥图标只在嫦娥消息旁显示。"));
        v0.entries.add(new ReleaseEntry("0.9", "新增嫦娥主动下发消息到元宵。"));
        v0.entries.add(new ReleaseEntry("0.9", "主动消息会显示在聊天页并触发通知。"));
        v0.entries.add(new ReleaseEntry("0.8", "主页面查询入口移入右上角菜单。"));
        v0.entries.add(new ReleaseEntry("0.8", "聊天记录搜索独立成新页面。"));
        v0.entries.add(new ReleaseEntry("0.7", "更换 Q 版嫦娥吃元宵应用图标。"));
        v0.entries.add(new ReleaseEntry("0.7", "明确图片消息进入嫦娥识图链路。"));
        v0.entries.add(new ReleaseEntry("0.6", "重做主界面视觉结构和输入区。"));
        v0.entries.add(new ReleaseEntry("0.6", "修复按钮文字显示不全。"));
        v0.entries.add(new ReleaseEntry("0.5", "统一构建包命名为 yuanxiao-版本号.apk。"));
        v0.entries.add(new ReleaseEntry("0.5", "新增应用内折叠修改记录。"));
        v0.entries.add(new ReleaseEntry("0.4", "新增聊天记录查找与结果跳转。"));
        v0.entries.add(new ReleaseEntry("0.4", "把服务器测试日志折叠到日志按钮。"));
        v0.entries.add(new ReleaseEntry("0.3", "新增图片选择、预览、压缩和发送。"));
        v0.entries.add(new ReleaseEntry("0.3", "新增嫦娥回复本地通知。"));
        v0.entries.add(new ReleaseEntry("0.2", "打通嫦娥到 Hermes 的桥接回复。"));
        v0.entries.add(new ReleaseEntry("0.1", "完成 HTTPS 文本通信 MVP。"));
        releaseGroups.add(v0);
    }

    private void toggleChangeLogPanel() {
        changeLogPanelVisible = !changeLogPanelVisible;
        changeLogPanel.setVisibility(changeLogPanelVisible ? View.VISIBLE : View.GONE);
        updateChangeLogButton();
        if (changeLogPanelVisible) {
            renderChangeLog();
        }
    }

    private void updateChangeLogButton() {
        if (changeLogButton != null) {
            changeLogButton.setText("记录 " + (changeLogPanelVisible ? "▲" : "▼"));
        }
    }

    private void toggleMenuPanel() {
        menuPanelVisible = !menuPanelVisible;
        if (menuPanel != null) {
            menuPanel.setVisibility(menuPanelVisible ? View.VISIBLE : View.GONE);
        }
        updateMenuButton();
    }

    private void updateMenuButton() {
        if (menuButton != null) {
            menuButton.setText(menuPanelVisible ? "菜单 ▲" : "菜单 ▼");
        }
    }

    private void toggleComposerOptionsPanel() {
        composerOptionsVisible = !composerOptionsVisible;
        if (composerOptionsPanel != null) {
            composerOptionsPanel.setVisibility(composerOptionsVisible ? View.VISIBLE : View.GONE);
        }
        updateComposerOptionsButton();
    }

    private void updateComposerOptionsButton() {
        if (composerOptionsButton == null) {
            return;
        }
        String target = TARGET_CODEX.equals(selectedChatTarget) ? "Codex" : "Hermes";
        composerOptionsButton.setText("选项 · " + target + (composerOptionsVisible ? " ▲" : " ▼"));
    }

    private void openSearchPage() {
        Intent intent = new Intent(this, SearchActivity.class);
        intent.putExtra(SearchActivity.EXTRA_CHAT_HISTORY, exportChatHistory());
        startActivity(intent);
    }

    private ArrayList<String> exportChatHistory() {
        ArrayList<String> records = new ArrayList<>();
        for (ChatRecord record : chatRecords) {
            records.add(record.searchText);
        }
        return records;
    }

    private void loadMainChatHistory() {
        mainChatHistory.clear();
        String raw = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_MAIN_CHAT_HISTORY, "[]");
        try {
            JSONArray array = new JSONArray(raw == null ? "[]" : raw);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.optJSONObject(i);
                MainChatMessage message = mainChatMessageFromJson(item);
                if (message != null) {
                    mainChatHistory.add(message);
                }
            }
        } catch (Exception exception) {
            mainChatHistory.clear();
            appendLog("聊天历史读取失败，已从空白历史继续。");
        }
        trimMainChatHistory();
    }

    private void renderMainChatHistory() {
        if (messageList == null) {
            return;
        }
        messageList.removeAllViews();
        chatRecords.clear();
        for (MainChatMessage item : mainChatHistory) {
            appendTextMessageTo(
                    messageList,
                    scrollView,
                    chatRecords,
                    item.speaker,
                    item.text,
                    item.mine,
                    null,
                    item.attachments,
                    false,
                    item.timeLabel
            );
        }
        scrollToBottom(scrollView);
    }

    private void rememberMainChatMessage(
            String speaker,
            String text,
            boolean mine,
            Bitmap bitmap,
            List<MessageAttachment> attachments,
            String timeLabel
    ) {
        List<MessageAttachment> savedAttachments = copyPersistableAttachments(attachments);
        if (bitmap != null) {
            savedAttachments.add(MessageAttachment.image("图片", "", "", null));
        }
        mainChatHistory.add(new MainChatMessage(
                speaker,
                limitHistoryText(text),
                mine,
                timeLabel,
                savedAttachments
        ));
        trimMainChatHistory();
        saveMainChatHistory();
    }

    private String limitHistoryText(String text) {
        String value = text == null ? "" : text;
        if (value.length() <= MAX_MAIN_CHAT_HISTORY_TEXT_CHARS) {
            return value;
        }
        return value.substring(0, MAX_MAIN_CHAT_HISTORY_TEXT_CHARS).trim() + "\n\n…（历史记录已截断）";
    }

    private List<MessageAttachment> copyPersistableAttachments(List<MessageAttachment> attachments) {
        List<MessageAttachment> copy = new ArrayList<>();
        if (attachments == null) {
            return copy;
        }
        for (MessageAttachment attachment : attachments) {
            if (attachment == null) {
                continue;
            }
            String dataUrl = attachment.dataUrl;
            if (dataUrl.length() > MAX_MAIN_CHAT_ATTACHMENT_DATA_CHARS) {
                dataUrl = "";
            }
            copy.add(new MessageAttachment(
                    attachment.type,
                    attachment.name,
                    attachment.url,
                    dataUrl,
                    attachment.mimeType,
                    attachment.size,
                    null
            ));
        }
        return copy;
    }

    private void trimMainChatHistory() {
        while (mainChatHistory.size() > MAX_MAIN_CHAT_HISTORY_MESSAGES) {
            mainChatHistory.remove(0);
        }
    }

    private void saveMainChatHistory() {
        JSONArray array = new JSONArray();
        for (MainChatMessage message : mainChatHistory) {
            array.put(mainChatMessageToJson(message));
        }
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putString(KEY_MAIN_CHAT_HISTORY, array.toString())
                .apply();
    }

    private JSONObject mainChatMessageToJson(MainChatMessage message) {
        JSONObject item = new JSONObject();
        try {
            item.put("speaker", message.speaker);
            item.put("text", message.text);
            item.put("mine", message.mine);
            item.put("time_label", message.timeLabel);
            JSONArray attachments = new JSONArray();
            for (MessageAttachment attachment : message.attachments) {
                attachments.put(attachmentToJson(attachment));
            }
            item.put("attachments", attachments);
        } catch (Exception ignored) {
        }
        return item;
    }

    private MainChatMessage mainChatMessageFromJson(JSONObject item) {
        if (item == null) {
            return null;
        }
        String speaker = item.optString("speaker", "").trim();
        if (speaker.isEmpty()) {
            speaker = item.optBoolean("mine", false) ? "我" : "嫦娥";
        }
        return new MainChatMessage(
                speaker,
                item.optString("text", ""),
                item.optBoolean("mine", false),
                item.optString("time_label", ""),
                attachmentsFromJson(item.optJSONArray("attachments"))
        );
    }

    private JSONObject attachmentToJson(MessageAttachment attachment) {
        JSONObject item = new JSONObject();
        try {
            item.put("type", attachment.type);
            item.put("name", attachment.name);
            item.put("url", attachment.url);
            item.put("data_url", attachment.dataUrl);
            item.put("mime_type", attachment.mimeType);
            item.put("size", attachment.size);
        } catch (Exception ignored) {
        }
        return item;
    }

    private void renderChangeLog() {
        if (changeLogList == null) {
            return;
        }
        changeLogList.removeAllViews();
        for (ReleaseGroup group : releaseGroups) {
            TextView groupButton = makeActionChip(
                    group.title + "  " + group.entries.size() + " 项  " + (group.expanded ? "▼" : "▶"),
                    Color.rgb(236, 243, 249),
                    Color.rgb(38, 83, 111)
            );
            groupButton.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            groupButton.setPadding(dp(12), 0, dp(12), 0);
            groupButton.setOnClickListener(view -> {
                group.expanded = !group.expanded;
                renderChangeLog();
            });
            changeLogList.addView(groupButton, new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
            ));

            if (!group.expanded) {
                continue;
            }
            for (ReleaseEntry entry : group.entries) {
                LinearLayout row = new LinearLayout(this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                row.setGravity(Gravity.CENTER_VERTICAL);
                row.setPadding(0, dp(5), 0, dp(5));

                TextView version = new TextView(this);
                version.setText("v" + entry.version);
                version.setTextSize(13);
                version.setTypeface(Typeface.DEFAULT_BOLD);
                version.setTextColor(Color.rgb(31, 111, 235));
                row.addView(version, new LinearLayout.LayoutParams(dp(48), LinearLayout.LayoutParams.WRAP_CONTENT));

                TextView summary = new TextView(this);
                summary.setText(entry.summary);
                summary.setTextSize(13);
                summary.setTextColor(Color.rgb(43, 50, 63));
                row.addView(summary, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
                changeLogList.addView(row, new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT
                ));
            }
        }
    }

    private void checkHealth() {
        setBusy(true);
        appendLog("测试嫦娥服务器连接。");
        executor.execute(() -> {
            try {
                JSONObject response = getJson(HEALTH_URL);
                appendLogFromWorker("嫦娥服务器在线：" + response.optString("service") + "，模式 " + response.optString("mode", "relay"));
            } catch (Exception exception) {
                appendLogFromWorker("连接失败：" + exception.getMessage());
            } finally {
                runOnUiThread(() -> setBusy(false));
            }
        });
    }

    private void startInboxPolling() {
        if (inboxPolling) {
            return;
        }
        inboxPolling = true;
        inboxHandler.post(inboxPollRunnable);
    }

    private void stopInboxPolling() {
        inboxPolling = false;
        inboxHandler.removeCallbacks(inboxPollRunnable);
    }

    private void pollInboxOnce() {
        if (inboxSyncInFlight) {
            return;
        }
        inboxSyncInFlight = true;
        executor.execute(() -> {
            try {
                String targetUrl = INBOX_URL;
                if (lastInboxMessageId != null && !lastInboxMessageId.isEmpty()) {
                    targetUrl += "?after=" + URLEncoder.encode(lastInboxMessageId, "UTF-8");
                }
                JSONObject response = getJson(targetUrl);
                JSONArray messages = response.optJSONArray("messages");
                if (messages != null) {
                    for (int i = 0; i < messages.length(); i++) {
                        JSONObject message = messages.optJSONObject(i);
                        if (message == null) {
                            continue;
                        }
                        handleInboxMessage(message);
                    }
                }
                inboxErrorLogged = false;
            } catch (Exception exception) {
                if (!inboxErrorLogged) {
                    inboxErrorLogged = true;
                    appendLogFromWorker("嫦娥主动消息同步失败：" + exception.getMessage());
                }
            } finally {
                inboxSyncInFlight = false;
            }
        });
    }

    private void handleInboxMessage(JSONObject message) {
        String id = message.optString("id", "");
        if (id.isEmpty() || id.equals(lastInboxMessageId)) {
            return;
        }
        String speaker = message.optString("speaker", "嫦娥");
        String text = message.optString("text", "");
        List<MessageAttachment> attachments = attachmentsFromMessage(message);
        if (text.trim().isEmpty() && attachments.isEmpty()) {
            lastInboxMessageId = id;
            saveLastInboxMessageId();
            return;
        }
        lastInboxMessageId = id;
        saveLastInboxMessageId();
        runOnUiThread(() -> {
            appendTextMessage(speaker, text, false, null, attachments);
            appendLog("收到嫦娥主动下发消息。");
            showIncomingNotification("嫦娥主动消息", text.isEmpty() ? "收到附件消息" : text, hasImageAttachment(attachments));
        });
    }

    private void saveLastInboxMessageId() {
        SharedPreferences preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        preferences.edit().putString(KEY_LAST_INBOX_ID, lastInboxMessageId).apply();
    }

    private void pickImage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_PICK_IMAGE);
    }

    private String normalizeChatTarget(String target) {
        if (TARGET_CODEX.equalsIgnoreCase(target == null ? "" : target.trim())) {
            return TARGET_CODEX;
        }
        return TARGET_HERMES;
    }

    private void setChatTarget(String target, boolean userInitiated) {
        selectedChatTarget = normalizeChatTarget(target);
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putString(KEY_CHAT_TARGET, selectedChatTarget)
                .apply();
        updateChatTargetButtons();
        if (userInitiated) {
            appendLog(TARGET_CODEX.equals(selectedChatTarget) ? "已切换到 Codex 专业。" : "已切换到 Hermes 日常。");
        }
    }

    private void openCodexSessionChat(JSONObject session) {
        String sessionId = session.optString("id", "").trim();
        if (sessionId.isEmpty()) {
            appendLog("这个 Codex 会话没有可用 session id。");
            return;
        }
        selectedCodexSessionId = sessionId;
        selectedCodexSessionTitle = session.optString("title", "未命名会话").trim();
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putString(KEY_CODEX_SESSION_ID, selectedCodexSessionId)
                .putString(KEY_CODEX_SESSION_TITLE, selectedCodexSessionTitle)
                .apply();
        showSessionChat();
        appendLog("已进入独立 Codex session：" + compactSessionTitle(selectedCodexSessionTitle));
    }

    private void clearSelectedCodexSession(boolean userInitiated) {
        selectedCodexSessionId = "";
        selectedCodexSessionTitle = "";
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .remove(KEY_CODEX_SESSION_ID)
                .remove(KEY_CODEX_SESSION_TITLE)
                .apply();
        updateCodexSessionLabel();
        updateSessionHeader();
        if (userInitiated) {
            appendLog("已清除当前 Codex session。");
        }
    }

    private void updateSessionHeader() {
        if (sessionTitle == null || sessionSubtitle == null) {
            return;
        }
        String title = compactSessionTitle(selectedCodexSessionTitle);
        sessionTitle.setText(title);
        sessionSubtitle.setText(selectedCodexSessionId.isEmpty() ? "未选择会话" : selectedCodexSessionId);
        if (sessionRenameButton != null) {
            sessionRenameButton.setEnabled(!selectedCodexSessionId.isEmpty() && !sessionSendInFlight);
        }
    }

    private void reloadCurrentSessionChat() {
        if (selectedCodexSessionId.isEmpty()) {
            appendLog("先从 Dashboard 选择一个 Codex session。");
            return;
        }
        sessionChatHistories.remove(selectedCodexSessionId);
        renderCurrentSessionHistory();
        setSessionDeliverySyncing();
        syncCurrentSessionMessages(true);
        appendLog("正在从 Mac mini 同步当前 session 历史。");
    }

    private void renderCurrentSessionHistory() {
        if (sessionMessageList == null) {
            return;
        }
        sessionMessageList.removeAllViews();
        sessionChatRecords.clear();
        if (selectedCodexSessionId.isEmpty()) {
            TextView empty = makeSessionEmptyState("未选择 Codex session");
            sessionMessageList.addView(empty, matchWrap());
            return;
        }
        List<SessionChatMessage> history = sessionChatHistories.get(selectedCodexSessionId);
        if (history == null || history.isEmpty()) {
            TextView empty = makeSessionEmptyState("暂无本地记录，正在同步 Mac mini 历史...");
            sessionMessageList.addView(empty, matchWrap());
            return;
        }
        for (SessionChatMessage item : history) {
            appendTextMessageTo(
                    sessionMessageList,
                    sessionScrollView,
                    sessionChatRecords,
                    item.speaker,
                    item.text,
                    item.mine,
                    null,
                    item.attachments,
                    false
            );
        }
        scrollToBottom(sessionScrollView);
    }

    private void appendSessionRenderedMessages(List<SessionChatMessage> messages) {
        if (messages == null || messages.isEmpty() || sessionMessageList == null) {
            return;
        }
        if (sessionMessageList.getChildCount() == 1 && sessionChatRecords.isEmpty()) {
            sessionMessageList.removeAllViews();
        }
        for (SessionChatMessage item : messages) {
            appendTextMessageTo(
                    sessionMessageList,
                    sessionScrollView,
                    sessionChatRecords,
                    item.speaker,
                    item.text,
                    item.mine,
                    null,
                    item.attachments,
                    false
            );
        }
        scrollToBottom(sessionScrollView);
    }

    private SessionMergeResult mergeSessionMessagesFromJson(String sessionId, JSONArray messages) {
        SessionMergeResult result = new SessionMergeResult();
        if (messages == null || sessionId == null || sessionId.isEmpty()) {
            return result;
        }
        List<SessionChatMessage> history = sessionChatHistories.get(sessionId);
        if (history == null) {
            history = new ArrayList<>();
            sessionChatHistories.put(sessionId, history);
        }
        for (int i = 0; i < messages.length(); i++) {
            JSONObject item = messages.optJSONObject(i);
            SessionChatMessage incoming = sessionMessageFromJson(item);
            if (incoming == null) {
                continue;
            }
            if (findSessionMessageById(history, incoming.id) != null) {
                continue;
            }
            SessionChatMessage localMatch = findMatchingLocalSessionMessage(history, incoming);
            if (localMatch != null) {
                localMatch.id = incoming.id;
                localMatch.speaker = incoming.speaker;
                localMatch.text = incoming.text;
                localMatch.mine = incoming.mine;
                localMatch.attachments = incoming.attachments;
                localMatch.order = incoming.order;
                localMatch.createdAt = incoming.createdAt;
                result.changed = true;
                result.needsFullRender = true;
                continue;
            }
            history.add(incoming);
            result.appendedMessages.add(incoming);
            result.changed = true;
            result.addedCount++;
            if (!incoming.mine) {
                result.hasNewAssistantMessage = true;
                result.newestAssistantText = incoming.text;
            }
        }
        if (result.changed) {
            Collections.sort(history, Comparator.comparingLong(message -> message.order));
            if (trimSessionHistory(history)) {
                result.needsFullRender = true;
            }
        }
        return result;
    }

    private boolean trimSessionHistory(List<SessionChatMessage> history) {
        if (history == null) {
            return false;
        }
        boolean removed = false;
        while (history.size() > MAX_SESSION_HISTORY_MESSAGES) {
            history.remove(0);
            removed = true;
        }
        return removed;
    }

    private SessionChatMessage sessionMessageFromJson(JSONObject item) {
        if (item == null) {
            return null;
        }
        String text = item.optString("text", "").trim();
        List<MessageAttachment> attachments = attachmentsFromMessage(item);
        if (text.isEmpty() && attachments.isEmpty()) {
            return null;
        }
        String role = item.optString("role", "");
        String speaker = item.optString("speaker", "");
        boolean mine = "user".equals(role) || "我".equals(speaker);
        if (speaker.trim().isEmpty()) {
            speaker = mine ? "我" : "Codex";
        }
        String id = item.optString("id", "");
        long order = item.optLong("order", Long.MAX_VALUE / 2);
        String createdAt = item.optString("created_at", "");
        return new SessionChatMessage(id, speaker, text, mine, attachments, order, createdAt);
    }

    private SessionChatMessage findSessionMessageById(List<SessionChatMessage> history, String id) {
        if (id == null || id.isEmpty()) {
            return null;
        }
        for (SessionChatMessage item : history) {
            if (id.equals(item.id)) {
                return item;
            }
        }
        return null;
    }

    private SessionChatMessage findMatchingLocalSessionMessage(List<SessionChatMessage> history, SessionChatMessage incoming) {
        String incomingText = sessionTextKey(incoming.text);
        if (incomingText.isEmpty()) {
            return null;
        }
        for (SessionChatMessage item : history) {
            if (item.id == null || !item.id.startsWith("local-")) {
                continue;
            }
            if (item.mine == incoming.mine && incomingText.equals(sessionTextKey(item.text))) {
                return item;
            }
        }
        return null;
    }

    private long currentSessionRemoteCursor(String sessionId) {
        List<SessionChatMessage> history = sessionChatHistories.get(sessionId);
        if (history == null || history.isEmpty()) {
            return 0L;
        }
        long cursor = 0L;
        for (SessionChatMessage item : history) {
            if (item.id == null || item.id.startsWith("local-")) {
                continue;
            }
            if (item.order > cursor && item.order < Long.MAX_VALUE / 2) {
                cursor = item.order;
            }
        }
        return cursor;
    }

    private String sessionTextKey(String text) {
        return (text == null ? "" : text).replaceAll("\\s+", " ").trim();
    }

    private TextView makeSessionEmptyState(String text) {
        TextView empty = new TextView(this);
        empty.setText(text);
        empty.setTextSize(14);
        empty.setTextColor(Color.rgb(104, 112, 126));
        empty.setGravity(Gravity.CENTER);
        empty.setPadding(dp(12), dp(28), dp(12), dp(28));
        return empty;
    }

    private void updateChatTargetButtons() {
        if (hermesTargetButton == null || codexTargetButton == null) {
            return;
        }
        boolean codexSelected = TARGET_CODEX.equals(selectedChatTarget);
        styleTargetButton(hermesTargetButton, !codexSelected);
        styleTargetButton(codexTargetButton, codexSelected);
        if (input != null) {
            input.setHint(codexSelected ? "给嫦娥发专业问题..." : "给嫦娥发消息...");
        }
        updateCodexSessionLabel();
        updateComposerOptionsButton();
    }

    private void updateCodexSessionLabel() {
        if (codexSessionLabel == null || clearCodexSessionButton == null) {
            return;
        }
        boolean codexSelected = TARGET_CODEX.equals(selectedChatTarget);
        clearCodexSessionButton.setVisibility(View.GONE);
        if (!codexSelected) {
            codexSessionLabel.setText("当前：Hermes 日常");
            codexSessionLabel.setTextColor(Color.rgb(91, 102, 118));
            codexSessionLabel.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(13), 1, Color.rgb(226, 232, 240)));
            clearCodexSessionButton.setEnabled(false);
            clearCodexSessionButton.setTextColor(Color.rgb(150, 158, 171));
            return;
        }
        codexSessionLabel.setText("当前：Codex 临时问答");
        codexSessionLabel.setTextColor(Color.rgb(91, 102, 118));
        codexSessionLabel.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(13), 1, Color.rgb(226, 232, 240)));
        clearCodexSessionButton.setEnabled(false);
        clearCodexSessionButton.setTextColor(Color.rgb(150, 158, 171));
    }

    private String compactSessionTitle(String title) {
        String value = title == null ? "" : title.trim();
        if (value.isEmpty()) {
            value = selectedCodexSessionId.isEmpty() ? "未命名会话" : selectedCodexSessionId;
        }
        return value.length() > 24 ? value.substring(0, 21) + "..." : value;
    }

    private void styleTargetButton(TextView button, boolean selected) {
        if (selected) {
            button.setTextColor(Color.WHITE);
            button.setBackground(makePanelBackground(Color.rgb(31, 111, 235), dp(14), 0, Color.TRANSPARENT));
        } else {
            button.setTextColor(Color.rgb(58, 70, 88));
            button.setBackground(makePanelBackground(Color.rgb(244, 247, 252), dp(14), 1, Color.rgb(224, 231, 240)));
        }
    }

    private String chatTargetDisplayName() {
        if (!TARGET_CODEX.equals(selectedChatTarget)) {
            return "Hermes 日常";
        }
        return "Codex 专业";
    }

    private void sendMessage() {
        String message = input.getText().toString().trim();
        String imageBase64 = pendingImageBase64;
        String imageMimeType = pendingImageMimeType;
        Bitmap imageBitmap = pendingImageBitmap;
        boolean hasImage = imageBase64 != null && !imageBase64.isEmpty();
        String chatTarget = selectedChatTarget;

        if (message.isEmpty() && !hasImage) {
            appendLog("先写点内容或选择一张图片再发送。");
            return;
        }

        input.setText("");
        clearSelectedImage();
        setBusy(true);
        setDeliverySending(hasImage ? "嫦娥识图" : chatTargetDisplayName());
        appendTextMessage("我", message.isEmpty() ? "[图片]" : message, true, imageBitmap);
        appendLog(hasImage ? "正在发送到嫦娥识图..." : "正在发送到 " + chatTargetDisplayName() + "...");

        executor.execute(() -> {
            try {
                JSONObject request = new JSONObject();
                request.put("message", message);
                request.put("target", chatTarget);
                request.put("route", chatTarget);
                request.put("conversation", MAIN_CHAT_CONVERSATION);
                if (hasImage) {
                    request.put("image_base64", imageBase64);
                    request.put("image_mime_type", imageMimeType == null ? "image/jpeg" : imageMimeType);
                    request.put("image_name", "yuanxiao-image.jpg");
                }
                JSONObject response = postJson(CHAT_URL, request, () -> setDeliveryAcceptedFromWorker());
                handleChatResponse(response);
            } catch (Exception exception) {
                setDeliveryFailedFromWorker();
                appendFromWorker("发送失败：" + exception.getMessage());
            } finally {
                runOnUiThread(() -> setBusy(false));
            }
        });
    }

    private void handleChatResponse(JSONObject response) throws Exception {
        String reply = response.optString("reply", "收到。");
        if (response.optBoolean("received_image", false)) {
            appendLogFromWorker("嫦娥识图完成。");
        }

        List<MessageAttachment> attachments = attachmentsFromJson(response.optJSONArray("files"));
        attachments.addAll(attachmentsFromJson(response.optJSONArray("attachments")));
        JSONArray images = response.optJSONArray("images");
        int imageCount = 0;
        if (images != null) {
            for (int i = 0; i < images.length(); i++) {
                JSONObject image = images.optJSONObject(i);
                if (image == null) {
                    continue;
                }
                Bitmap bitmap = decodeImageResponse(image);
                if (bitmap != null) {
                    imageCount++;
                    String name = image.optString("name", image.optString("alt", "图片"));
                    attachments.add(MessageAttachment.image(name, image.optString("url", ""), image.optString("data_url", ""), bitmap));
                } else {
                    String url = image.optString("url", image.optString("data_url", ""));
                    if (!url.isEmpty()) {
                        imageCount++;
                        attachments.add(MessageAttachment.image(image.optString("name", "图片"), url, image.optString("data_url", ""), null));
                    }
                }
            }
        }
        List<MessageAttachment> finalAttachments = attachments;
        int finalImageCount = imageCount;
        runOnUiThread(() -> {
            appendTextMessage("嫦娥", reply, false, null, finalAttachments);
            showIncomingNotification("嫦娥有新回复", reply, finalImageCount > 0);
            setDeliveryReplied();
        });
    }

    private void sendSessionMessage() {
        String sessionId = selectedCodexSessionId;
        String message = sessionInput == null ? "" : sessionInput.getText().toString().trim();
        if (sessionId.isEmpty()) {
            appendLog("先从 Dashboard 选择一个 Codex session。");
            return;
        }
        if (message.isEmpty()) {
            appendLog("先写点内容再发送到 Codex session。");
            return;
        }

        sessionInput.setText("");
        setSessionBusy(true);
        setSessionDeliverySending();
        appendSessionTextMessage(sessionId, "我", message, true, null, new ArrayList<>());
        appendLog("正在发送到 Codex session：" + compactSessionTitle(selectedCodexSessionTitle));

        executor.execute(() -> {
            try {
                JSONObject request = new JSONObject();
                request.put("message", message);
                request.put("target", TARGET_CODEX);
                request.put("route", TARGET_CODEX);
                request.put("conversation", "codex-session-" + sessionId);
                request.put("codex_session_id", sessionId);
                JSONObject response = postJson(CHAT_URL, request, () -> setSessionDeliveryAcceptedFromWorker());
                handleSessionChatResponse(sessionId, response);
            } catch (Exception exception) {
                setSessionDeliveryFailedFromWorker();
                appendLogFromWorker("Codex session 发送失败：" + exception.getMessage());
                runOnUiThread(() -> appendSessionTextMessage(
                        sessionId,
                        "系统",
                        "发送失败：" + exception.getMessage(),
                        false,
                        null,
                        new ArrayList<>()
                ));
            } finally {
                runOnUiThread(() -> {
                    setSessionBusy(false);
                    syncCurrentSessionMessages(false);
                });
            }
        });
    }

    private void handleSessionChatResponse(String sessionId, JSONObject response) throws Exception {
        String reply = response.optString("reply", "收到。");
        List<MessageAttachment> attachments = attachmentsFromJson(response.optJSONArray("files"));
        attachments.addAll(attachmentsFromJson(response.optJSONArray("attachments")));
        JSONArray images = response.optJSONArray("images");
        int imageCount = 0;
        if (images != null) {
            for (int i = 0; i < images.length(); i++) {
                JSONObject image = images.optJSONObject(i);
                if (image == null) {
                    continue;
                }
                Bitmap bitmap = decodeImageResponse(image);
                if (bitmap != null) {
                    imageCount++;
                    String name = image.optString("name", image.optString("alt", "图片"));
                    attachments.add(MessageAttachment.image(name, image.optString("url", ""), image.optString("data_url", ""), bitmap));
                } else {
                    String url = image.optString("url", image.optString("data_url", ""));
                    if (!url.isEmpty()) {
                        imageCount++;
                        attachments.add(MessageAttachment.image(image.optString("name", "图片"), url, image.optString("data_url", ""), null));
                    }
                }
            }
        }
        List<MessageAttachment> finalAttachments = attachments;
        int finalImageCount = imageCount;
        runOnUiThread(() -> {
            appendSessionTextMessage(sessionId, "Codex", reply, false, null, finalAttachments);
            showIncomingNotification("Codex session 已回复", reply, finalImageCount > 0);
            setSessionDeliveryReplied();
        });
    }

    private JSONObject getJson(String targetUrl) throws Exception {
        HttpsURLConnection connection = openConnection(targetUrl);
        connection.setRequestMethod("GET");
        return readJson(connection);
    }

    private JSONObject postJson(String targetUrl, JSONObject payload) throws Exception {
        return postJson(targetUrl, payload, null);
    }

    private JSONObject postJson(String targetUrl, JSONObject payload, Runnable acceptedCallback) throws Exception {
        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        HttpsURLConnection connection = openConnection(targetUrl);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Content-Length", String.valueOf(body.length));
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }
        return readJson(connection, acceptedCallback);
    }

    private HttpsURLConnection openConnection(String targetUrl) throws Exception {
        URL url = new URL(targetUrl);
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setConnectTimeout(10_000);
        connection.setReadTimeout(900_000);
        return connection;
    }

    private JSONObject readJson(HttpsURLConnection connection) throws Exception {
        return readJson(connection, null);
    }

    private JSONObject readJson(HttpsURLConnection connection, Runnable acceptedCallback) throws Exception {
        int code = connection.getResponseCode();
        if (code < 400 && acceptedCallback != null) {
            acceptedCallback.run();
        }
        InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
        if (stream == null) {
            throw new IllegalStateException("HTTP " + code);
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));
        StringBuilder builder = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            builder.append(line);
        }
        if (code >= 400) {
            throw new IllegalStateException("HTTP " + code + " " + builder);
        }
        return new JSONObject(builder.toString());
    }

    private ImagePayload buildImagePayload(Uri uri) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream stream = getContentResolver().openInputStream(uri)) {
            BitmapFactory.decodeStream(stream, null, bounds);
        }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            throw new IllegalStateException("无法读取图片尺寸");
        }

        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = calculateInSampleSize(bounds.outWidth, bounds.outHeight, MAX_IMAGE_EDGE);
        Bitmap decoded;
        try (InputStream stream = getContentResolver().openInputStream(uri)) {
            decoded = BitmapFactory.decodeStream(stream, null, options);
        }
        if (decoded == null) {
            throw new IllegalStateException("无法读取图片");
        }

        Bitmap scaled = scaleBitmap(decoded, MAX_IMAGE_EDGE);
        if (scaled != decoded) {
            decoded.recycle();
        }

        byte[] bytes = compressForHermes(scaled);
        Bitmap preview = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        return new ImagePayload(preview, Base64.encodeToString(bytes, Base64.NO_WRAP), "image/jpeg", bytes.length);
    }

    private int calculateInSampleSize(int width, int height, int maxEdge) {
        int sample = 1;
        while ((width / sample) > maxEdge * 2 || (height / sample) > maxEdge * 2) {
            sample *= 2;
        }
        return sample;
    }

    private Bitmap scaleBitmap(Bitmap source, int maxEdge) {
        int width = source.getWidth();
        int height = source.getHeight();
        int largest = Math.max(width, height);
        if (largest <= maxEdge) {
            return source;
        }
        float scale = maxEdge / (float) largest;
        int scaledWidth = Math.max(1, Math.round(width * scale));
        int scaledHeight = Math.max(1, Math.round(height * scale));
        return Bitmap.createScaledBitmap(source, scaledWidth, scaledHeight, true);
    }

    private byte[] compressForHermes(Bitmap bitmap) {
        int quality = 82;
        byte[] bytes = compressJpeg(bitmap, quality);
        while (bytes.length > MAX_HERMES_IMAGE_BYTES && quality > 46) {
            quality -= 8;
            bytes = compressJpeg(bitmap, quality);
        }
        Bitmap current = bitmap;
        while (bytes.length > MAX_HERMES_IMAGE_BYTES && Math.max(current.getWidth(), current.getHeight()) > 420) {
            current = Bitmap.createScaledBitmap(
                    current,
                    Math.max(1, Math.round(current.getWidth() * 0.82f)),
                    Math.max(1, Math.round(current.getHeight() * 0.82f)),
                    true
            );
            bytes = compressJpeg(current, 54);
        }
        return bytes;
    }

    private byte[] compressJpeg(Bitmap bitmap, int quality) {
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, outputStream);
        return outputStream.toByteArray();
    }

    private Bitmap decodeImageResponse(JSONObject image) throws Exception {
        String dataUrl = image.optString("data_url", "");
        if (dataUrl.startsWith("data:image/") && dataUrl.contains(",")) {
            String base64 = dataUrl.substring(dataUrl.indexOf(',') + 1);
            byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        }

        String url = image.optString("url", "");
        if (url.startsWith("http://") || url.startsWith("https://")) {
            try (InputStream stream = new URL(url).openStream()) {
                return BitmapFactory.decodeStream(stream);
            }
        }
        return null;
    }

    private void setSelectedImage(ImagePayload imagePayload) {
        pendingImageBitmap = imagePayload.bitmap;
        pendingImageBase64 = imagePayload.base64;
        pendingImageMimeType = imagePayload.mimeType;
        selectedImagePreview.setImageBitmap(imagePayload.bitmap);
        selectedImagePanel.setVisibility(View.VISIBLE);
        selectedImagePreview.setVisibility(View.VISIBLE);
        selectedImageLabel.setText("已选择图片，压缩后约 " + Math.max(1, imagePayload.sizeBytes / 1024) + " KB");
        selectedImageLabel.setVisibility(View.VISIBLE);
        clearImageButton.setVisibility(View.VISIBLE);
        appendLog("图片已就绪，可以发送给嫦娥。");
    }

    private void clearSelectedImage() {
        pendingImageBase64 = null;
        pendingImageMimeType = null;
        pendingImageBitmap = null;
        selectedImagePreview.setImageDrawable(null);
        selectedImagePanel.setVisibility(View.GONE);
        selectedImagePreview.setVisibility(View.GONE);
        selectedImageLabel.setText("");
        selectedImageLabel.setVisibility(View.GONE);
        clearImageButton.setVisibility(View.GONE);
    }

    private void setBusy(boolean busy) {
        sendButton.setEnabled(!busy);
        healthButton.setEnabled(!busy);
        imageButton.setEnabled(!busy);
        clearImageButton.setEnabled(!busy);
        if (hermesTargetButton != null) {
            hermesTargetButton.setEnabled(!busy);
        }
        if (codexTargetButton != null) {
            codexTargetButton.setEnabled(!busy);
        }
        if (clearCodexSessionButton != null) {
            clearCodexSessionButton.setEnabled(!busy && TARGET_CODEX.equals(selectedChatTarget) && !selectedCodexSessionId.isEmpty());
        }
        if (composerOptionsButton != null) {
            composerOptionsButton.setEnabled(!busy);
        }
        sendButton.setText(busy ? "等待" : "发送");
        healthButton.setText(busy ? "处理中" : "连接");
    }

    private void setSessionBusy(boolean busy) {
        sessionSendInFlight = busy;
        if (sessionSendButton != null) {
            sessionSendButton.setEnabled(!busy);
            sessionSendButton.setText(busy ? "等待" : "发送");
        }
        if (sessionClearButton != null) {
            sessionClearButton.setEnabled(!busy);
        }
        if (sessionRenameButton != null) {
            sessionRenameButton.setEnabled(!busy && !selectedCodexSessionId.isEmpty());
        }
    }

    private void setDeliverySending(String targetName) {
        setDeliveryStatus("发送中：" + targetName, Color.rgb(255, 248, 230), Color.rgb(139, 91, 20));
    }

    private void setDeliveryAccepted() {
        setDeliveryStatus("嫦娥已收到，等待回复", Color.rgb(231, 241, 255), Color.rgb(31, 96, 164));
    }

    private void setDeliveryReplied() {
        setDeliveryStatus("嫦娥已回复", Color.rgb(232, 246, 236), Color.rgb(42, 123, 70));
    }

    private void setDeliveryFailed() {
        setDeliveryStatus("发送失败，点击日志查看", Color.rgb(255, 238, 235), Color.rgb(163, 55, 43));
    }

    private void setDeliveryAcceptedFromWorker() {
        runOnUiThread(() -> setDeliveryAccepted());
    }

    private void setDeliveryFailedFromWorker() {
        runOnUiThread(() -> setDeliveryFailed());
    }

    private void setDeliveryStatus(String text, int backgroundColor, int textColor) {
        setDeliveryStatus(deliveryStatusBar, text, backgroundColor, textColor);
    }

    private void setSessionDeliveryReady() {
        setSessionDeliveryStatus("就绪", Color.rgb(244, 247, 252), Color.rgb(91, 102, 118));
    }

    private void setSessionDeliverySyncing() {
        setSessionDeliveryStatus("同步中：Mac mini 历史", Color.rgb(231, 241, 255), Color.rgb(31, 96, 164));
    }

    private void setSessionDeliverySynced() {
        setSessionDeliveryStatus("已同步 Mac mini 历史", Color.rgb(232, 246, 236), Color.rgb(42, 123, 70));
    }

    private void setSessionDeliverySending() {
        setSessionDeliveryStatus("发送中：Codex Session", Color.rgb(255, 248, 230), Color.rgb(139, 91, 20));
    }

    private void setSessionDeliveryAccepted() {
        setSessionDeliveryStatus("嫦娥已收到，等待 session 回复", Color.rgb(231, 241, 255), Color.rgb(31, 96, 164));
    }

    private void setSessionDeliveryReplied() {
        setSessionDeliveryStatus("Session 已回复", Color.rgb(232, 246, 236), Color.rgb(42, 123, 70));
    }

    private void setSessionDeliveryFailed() {
        setSessionDeliveryStatus("发送失败，点击日志查看", Color.rgb(255, 238, 235), Color.rgb(163, 55, 43));
    }

    private void setSessionDeliveryAcceptedFromWorker() {
        runOnUiThread(() -> setSessionDeliveryAccepted());
    }

    private void setSessionDeliveryFailedFromWorker() {
        runOnUiThread(() -> setSessionDeliveryFailed());
    }

    private void setSessionDeliveryStatus(String text, int backgroundColor, int textColor) {
        setDeliveryStatus(sessionDeliveryStatusBar, text, backgroundColor, textColor);
    }

    private void setDeliveryStatus(TextView targetBar, String text, int backgroundColor, int textColor) {
        if (targetBar == null) {
            return;
        }
        targetBar.setText("状态：" + text);
        targetBar.setTextColor(textColor);
        targetBar.setBackground(makePanelBackground(backgroundColor, dp(13), 1, Color.rgb(226, 232, 240)));
    }

    private void appendFromWorker(String line) {
        runOnUiThread(() -> appendSystemOrSpeakerLine(line));
    }

    private void appendLogFromWorker(String line) {
        runOnUiThread(() -> appendLog(line));
    }

    private void appendImageFromWorker(String speaker, Bitmap bitmap) {
        List<MessageAttachment> attachments = new ArrayList<>();
        attachments.add(MessageAttachment.image("图片", "", "", bitmap));
        runOnUiThread(() -> appendTextMessage(speaker, "", false, null, attachments));
    }

    private void appendSystemOrSpeakerLine(String line) {
        int split = line.indexOf('：');
        if (split > 0 && split < 6) {
            appendTextMessage(line.substring(0, split), line.substring(split + 1), false, null);
        } else {
            appendLog(line);
        }
    }

    private void appendLog(String text) {
        logCount++;
        logLines.add("[" + stamp() + "] " + text);
        while (logLines.size() > MAX_LOG_LINES) {
            logLines.remove(0);
        }
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < logLines.size(); i++) {
            if (i > 0) {
                builder.append('\n');
            }
            builder.append(logLines.get(i));
        }
        logText.setText(builder.toString());
        updateLogButton();
        if (logPanelVisible) {
            logPanel.post(() -> logPanel.fullScroll(View.FOCUS_DOWN));
        }
    }

    private void toggleLogPanel() {
        logPanelVisible = !logPanelVisible;
        logPanel.setVisibility(logPanelVisible ? View.VISIBLE : View.GONE);
        updateLogButton();
    }

    private void updateLogButton() {
        String suffix = logPanelVisible ? "▲" : "▼";
        logButton.setText("日志 " + logCount + " " + suffix);
    }

    private void appendTextMessage(String speaker, String text, boolean mine, Bitmap bitmap) {
        appendTextMessage(speaker, text, mine, bitmap, new ArrayList<>());
    }

    private void appendTextMessage(String speaker, String text, boolean mine, Bitmap bitmap, List<MessageAttachment> attachments) {
        String timeLabel = stamp();
        rememberMainChatMessage(speaker, text, mine, bitmap, attachments, timeLabel);
        appendTextMessageTo(messageList, scrollView, chatRecords, speaker, text, mine, bitmap, attachments, true, timeLabel);
    }

    private void appendSessionTextMessage(
            String sessionId,
            String speaker,
            String text,
            boolean mine,
            Bitmap bitmap,
            List<MessageAttachment> attachments
    ) {
        if (sessionId == null || sessionId.isEmpty()) {
            return;
        }
        List<MessageAttachment> savedAttachments = attachments == null ? new ArrayList<>() : new ArrayList<>(attachments);
        List<SessionChatMessage> history = sessionChatHistories.get(sessionId);
        if (history == null) {
            history = new ArrayList<>();
            sessionChatHistories.put(sessionId, history);
        }
        history.add(new SessionChatMessage(
                "local-" + System.currentTimeMillis() + "-" + history.size(),
                speaker,
                text,
                mine,
                savedAttachments,
                Long.MAX_VALUE / 2 + System.currentTimeMillis() % 1_000_000L,
                nowLocalIso()
        ));
        boolean trimmed = trimSessionHistory(history);
        if (!sessionId.equals(selectedCodexSessionId) || !sessionChatVisible || sessionMessageList == null) {
            return;
        }
        if (trimmed) {
            renderCurrentSessionHistory();
            return;
        }
        if (sessionMessageList.getChildCount() == 1 && sessionChatRecords.isEmpty()) {
            sessionMessageList.removeAllViews();
        }
        appendTextMessageTo(sessionMessageList, sessionScrollView, sessionChatRecords, speaker, text, mine, bitmap, savedAttachments);
    }

    private void appendTextMessageTo(
            LinearLayout targetMessageList,
            ScrollView targetScrollView,
            List<ChatRecord> targetRecords,
            String speaker,
            String text,
            boolean mine,
            Bitmap bitmap,
            List<MessageAttachment> attachments
    ) {
        appendTextMessageTo(targetMessageList, targetScrollView, targetRecords, speaker, text, mine, bitmap, attachments, true);
    }

    private void appendTextMessageTo(
            LinearLayout targetMessageList,
            ScrollView targetScrollView,
            List<ChatRecord> targetRecords,
            String speaker,
            String text,
            boolean mine,
            Bitmap bitmap,
            List<MessageAttachment> attachments,
            boolean scrollAfterAppend
    ) {
        appendTextMessageTo(targetMessageList, targetScrollView, targetRecords, speaker, text, mine, bitmap, attachments, scrollAfterAppend, stamp());
    }

    private void appendTextMessageTo(
            LinearLayout targetMessageList,
            ScrollView targetScrollView,
            List<ChatRecord> targetRecords,
            String speaker,
            String text,
            boolean mine,
            Bitmap bitmap,
            List<MessageAttachment> attachments,
            boolean scrollAfterAppend,
            String timeLabel
    ) {
        if (targetMessageList == null || targetScrollView == null) {
            return;
        }
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(mine ? Gravity.END : Gravity.START);
        row.setPadding(0, dp(4), 0, dp(4));

        if (!mine && "嫦娥".equals(speaker)) {
            ImageView avatar = new ImageView(this);
            avatar.setImageResource(getApplicationInfo().icon);
            avatar.setScaleType(ImageView.ScaleType.CENTER_CROP);
            avatar.setBackground(makePanelBackground(Color.WHITE, dp(10), 1, Color.rgb(226, 232, 240)));
            LinearLayout.LayoutParams avatarParams = new LinearLayout.LayoutParams(dp(36), dp(36));
            avatarParams.rightMargin = dp(8);
            row.addView(avatar, avatarParams);
        }

        LinearLayout bubble = new LinearLayout(this);
        bubble.setOrientation(LinearLayout.VERTICAL);
        bubble.setPadding(dp(12), dp(8), dp(12), dp(8));
        bubble.setBackground(makeBubbleBackground(mine, false));

        TextView label = new TextView(this);
        String safeTime = timeLabel == null || timeLabel.trim().isEmpty() ? stamp() : timeLabel.trim();
        label.setText(speaker + " · " + safeTime);
        label.setTextSize(11);
        label.setTextColor(mine ? Color.rgb(219, 238, 255) : Color.rgb(116, 124, 137));
        bubble.addView(label);

        List<MessageAttachment> allAttachments = new ArrayList<>();
        if (attachments != null) {
            allAttachments.addAll(attachments);
        }
        if (bitmap != null) {
            allAttachments.add(MessageAttachment.image("图片", "", "", bitmap));
        }

        String messageText = text == null ? "" : text;
        renderRichContent(bubble, messageText, mine, allAttachments);

        TextView copyButton = makeCopyIconButton();
        String copyText = buildCopyText(messageText, allAttachments);
        copyButton.setOnClickListener(view -> copyMessageToClipboard(copyText));

        LinearLayout messageBlock = new LinearLayout(this);
        messageBlock.setOrientation(LinearLayout.VERTICAL);
        messageBlock.setGravity(Gravity.END);
        messageBlock.addView(bubble, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        LinearLayout copyRow = new LinearLayout(this);
        copyRow.setGravity(Gravity.END);
        LinearLayout.LayoutParams copyParams = new LinearLayout.LayoutParams(dp(32), dp(32));
        copyParams.topMargin = dp(3);
        copyParams.rightMargin = dp(2);
        copyRow.addView(copyButton, copyParams);
        messageBlock.addView(copyRow, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));

        LinearLayout.LayoutParams bubbleParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        bubbleParams.leftMargin = mine ? dp(48) : 0;
        bubbleParams.rightMargin = mine ? 0 : dp(48);
        row.addView(messageBlock, bubbleParams);
        targetMessageList.addView(row, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        ));
        if (targetRecords != null) {
            targetRecords.add(new ChatRecord(row, bubble, mine, (speaker + " " + messageText + " " + attachmentsSearchText(allAttachments)).toLowerCase(Locale.ROOT)));
        }
        if (scrollAfterAppend) {
            scrollToBottom(targetScrollView);
        }
    }

    private void renderRichContent(LinearLayout bubble, String text, boolean mine, List<MessageAttachment> attachments) {
        List<MessageAttachment> allAttachments = new ArrayList<>(attachments);
        String cleanText = extractMarkdownImageAttachments(text, allAttachments).trim();
        for (MessageAttachment attachment : extractFileLinks(cleanText)) {
            addAttachmentIfNew(allAttachments, attachment);
        }
        if (!cleanText.isEmpty()) {
            renderMarkdownBlocks(bubble, cleanText, mine);
        }
        for (MessageAttachment attachment : allAttachments) {
            renderAttachment(bubble, attachment, mine);
        }
    }

    private void renderMarkdownBlocks(LinearLayout bubble, String text, boolean mine) {
        String[] lines = text.replace("\r\n", "\n").split("\n", -1);
        StringBuilder paragraph = new StringBuilder();
        int index = 0;
        while (index < lines.length) {
            if (index + 1 < lines.length && looksLikeTableRow(lines[index]) && isTableSeparator(lines[index + 1])) {
                flushParagraph(bubble, paragraph, mine);
                List<String> tableLines = new ArrayList<>();
                tableLines.add(lines[index]);
                index += 2;
                while (index < lines.length && looksLikeTableRow(lines[index])) {
                    tableLines.add(lines[index]);
                    index++;
                }
                renderMarkdownTable(bubble, tableLines, mine);
                continue;
            }
            if (paragraph.length() > 0) {
                paragraph.append("\n");
            }
            paragraph.append(lines[index]);
            index++;
        }
        flushParagraph(bubble, paragraph, mine);
    }

    private void flushParagraph(LinearLayout bubble, StringBuilder paragraph, boolean mine) {
        String block = paragraph.toString().trim();
        paragraph.setLength(0);
        if (block.isEmpty()) {
            return;
        }
        TextView content = createRichTextView(block, mine);
        LinearLayout.LayoutParams params = matchWrap();
        params.topMargin = dp(4);
        bubble.addView(content, params);
    }

    private TextView createRichTextView(String markdown, boolean mine) {
        TextView content = new TextView(this);
        content.setText(markdownToSpanned(markdown));
        content.setTextSize(15);
        content.setTextColor(mine ? Color.WHITE : Color.rgb(28, 33, 43));
        content.setLinkTextColor(mine ? Color.rgb(210, 232, 255) : Color.rgb(31, 111, 235));
        content.setPadding(0, dp(3), 0, 0);
        content.setMovementMethod(LinkMovementMethod.getInstance());
        content.setLinksClickable(true);
        Linkify.addLinks(content, Linkify.WEB_URLS | Linkify.EMAIL_ADDRESSES);
        return content;
    }

    private Spanned markdownToSpanned(String markdown) {
        String cacheKey = markdown == null ? "" : markdown;
        Spanned cached = richTextCache.get(cacheKey);
        if (cached != null) {
            return cached;
        }
        String[] lines = markdown.split("\n", -1);
        StringBuilder html = new StringBuilder();
        for (int i = 0; i < lines.length; i++) {
            if (i > 0) {
                html.append("<br>");
            }
            html.append(markdownLineToHtml(lines[i]));
        }
        Spanned result;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            result = Html.fromHtml(html.toString(), Html.FROM_HTML_MODE_LEGACY);
        } else {
            result = Html.fromHtml(html.toString());
        }
        rememberRichText(cacheKey, result);
        return result;
    }

    private void rememberRichText(String key, Spanned value) {
        if (key.length() > 4000) {
            return;
        }
        richTextCache.put(key, value);
        richTextCacheKeys.add(key);
        while (richTextCacheKeys.size() > MAX_RICH_TEXT_CACHE_ENTRIES) {
            String oldest = richTextCacheKeys.remove(0);
            richTextCache.remove(oldest);
        }
    }

    private String markdownLineToHtml(String line) {
        String trimmed = line.trim();
        int heading = 0;
        while (heading < trimmed.length() && heading < 6 && trimmed.charAt(heading) == '#') {
            heading++;
        }
        if (heading > 0 && heading < trimmed.length() && trimmed.charAt(heading) == ' ') {
            return "<b>" + inlineMarkdownToHtml(trimmed.substring(heading + 1)) + "</b>";
        }
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            return "&bull; " + inlineMarkdownToHtml(trimmed.substring(2));
        }
        if (trimmed.matches("^\\d+\\.\\s+.*")) {
            return inlineMarkdownToHtml(trimmed);
        }
        return inlineMarkdownToHtml(line);
    }

    private String inlineMarkdownToHtml(String text) {
        StringBuilder linked = new StringBuilder();
        Matcher matcher = MARKDOWN_LINK_PATTERN.matcher(text);
        int cursor = 0;
        while (matcher.find()) {
            linked.append(escapeHtml(text.substring(cursor, matcher.start())));
            linked.append("<a href=\"")
                    .append(escapeHtmlAttribute(matcher.group(2)))
                    .append("\">")
                    .append(escapeHtml(matcher.group(1)))
                    .append("</a>");
            cursor = matcher.end();
        }
        linked.append(escapeHtml(text.substring(cursor)));
        String html = linked.toString();
        html = html.replaceAll("`([^`]+)`", "<tt>$1</tt>");
        html = html.replaceAll("\\*\\*([^*]+)\\*\\*", "<b>$1</b>");
        html = html.replaceAll("(?<!\\*)\\*([^*]+)\\*(?!\\*)", "<i>$1</i>");
        return html;
    }

    private String escapeHtml(String value) {
        return value.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;");
    }

    private String escapeHtmlAttribute(String value) {
        return escapeHtml(value).replace("\"", "&quot;");
    }

    private boolean looksLikeTableRow(String line) {
        return line != null && line.contains("|") && parseTableRow(line).size() >= 2;
    }

    private boolean isTableSeparator(String line) {
        if (!looksLikeTableRow(line)) {
            return false;
        }
        List<String> cells = parseTableRow(line);
        for (String cell : cells) {
            if (!cell.trim().matches(":?-{3,}:?")) {
                return false;
            }
        }
        return true;
    }

    private List<String> parseTableRow(String line) {
        String trimmed = line == null ? "" : line.trim();
        if (trimmed.startsWith("|")) {
            trimmed = trimmed.substring(1);
        }
        if (trimmed.endsWith("|")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        String[] parts = trimmed.split("\\|", -1);
        List<String> cells = new ArrayList<>();
        for (String part : parts) {
            cells.add(part.trim());
        }
        return cells;
    }

    private void renderMarkdownTable(LinearLayout bubble, List<String> tableLines, boolean mine) {
        HorizontalScrollView horizontalScrollView = new HorizontalScrollView(this);
        horizontalScrollView.setHorizontalScrollBarEnabled(false);
        LinearLayout table = new LinearLayout(this);
        table.setOrientation(LinearLayout.VERTICAL);
        table.setBackground(makePanelBackground(mine ? Color.rgb(28, 92, 184) : Color.rgb(248, 250, 253), dp(8), 1, mine ? Color.rgb(99, 154, 230) : Color.rgb(219, 225, 235)));

        List<List<String>> rows = normalizeTableRows(tableLines);
        int[] columnWidths = markdownTableColumnWidths(rows);

        for (int rowIndex = 0; rowIndex < rows.size(); rowIndex++) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setBaselineAligned(false);
            List<String> cells = rows.get(rowIndex);
            for (int columnIndex = 0; columnIndex < cells.size(); columnIndex++) {
                String cell = cells.get(columnIndex);
                TextView cellView = createRichTextView(cell, mine);
                cellView.setTextSize(13);
                cellView.setTypeface(rowIndex == 0 ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
                cellView.setGravity((rowIndex == 0 ? Gravity.CENTER : Gravity.START) | Gravity.CENTER_VERTICAL);
                cellView.setIncludeFontPadding(false);
                cellView.setSingleLine(false);
                cellView.setMinLines(1);
                cellView.setMaxLines(5);
                cellView.setPadding(dp(8), dp(7), dp(8), dp(7));
                cellView.setBackground(makePanelBackground(
                        rowIndex == 0
                                ? (mine ? Color.rgb(23, 81, 168) : Color.rgb(235, 241, 248))
                                : (mine ? Color.rgb(31, 111, 235) : Color.WHITE),
                        0,
                        1,
                        mine ? Color.rgb(99, 154, 230) : Color.rgb(226, 232, 240)
                ));
                row.addView(cellView, new LinearLayout.LayoutParams(dp(columnWidths[columnIndex]), LinearLayout.LayoutParams.WRAP_CONTENT));
            }
            table.addView(row);
        }

        horizontalScrollView.addView(table);
        LinearLayout.LayoutParams tableParams = matchWrap();
        tableParams.topMargin = dp(8);
        bubble.addView(horizontalScrollView, tableParams);
    }

    private List<List<String>> normalizeTableRows(List<String> tableLines) {
        List<List<String>> rows = new ArrayList<>();
        int columnCount = 0;
        for (String line : tableLines) {
            List<String> cells = parseTableRow(line);
            rows.add(cells);
            columnCount = Math.max(columnCount, cells.size());
        }
        for (List<String> row : rows) {
            while (row.size() < columnCount) {
                row.add("");
            }
        }
        return rows;
    }

    private int[] markdownTableColumnWidths(List<List<String>> rows) {
        int columnCount = rows.isEmpty() ? 0 : rows.get(0).size();
        int[] widths = new int[columnCount];
        for (int columnIndex = 0; columnIndex < columnCount; columnIndex++) {
            int units = 0;
            for (List<String> row : rows) {
                units = Math.max(units, tableTextUnits(row.get(columnIndex)));
            }
            widths[columnIndex] = Math.max(88, Math.min(176, 54 + units * 7));
        }
        return widths;
    }

    private int tableTextUnits(String text) {
        String clean = text == null ? "" : text.replaceAll("[*_`\\[\\]()]", "");
        int units = 0;
        for (int i = 0; i < clean.length(); i++) {
            char c = clean.charAt(i);
            units += c <= 127 ? 1 : 2;
        }
        return units;
    }

    private String extractMarkdownImageAttachments(String text, List<MessageAttachment> attachments) {
        Matcher matcher = MARKDOWN_IMAGE_PATTERN.matcher(text == null ? "" : text);
        StringBuffer clean = new StringBuffer();
        while (matcher.find()) {
            String name = matcher.group(1) == null || matcher.group(1).trim().isEmpty() ? "图片" : matcher.group(1).trim();
            String url = matcher.group(2) == null ? "" : matcher.group(2).trim();
            attachments.add(MessageAttachment.image(name, url, url.startsWith("data:image/") ? url : "", null));
            matcher.appendReplacement(clean, "");
        }
        matcher.appendTail(clean);
        return clean.toString();
    }

    private List<MessageAttachment> extractFileLinks(String text) {
        List<MessageAttachment> files = new ArrayList<>();
        Matcher markdownLinks = MARKDOWN_LINK_PATTERN.matcher(text == null ? "" : text);
        while (markdownLinks.find()) {
            String name = markdownLinks.group(1).trim();
            String url = markdownLinks.group(2).trim();
            if (looksLikeFileUrl(url)) {
                files.add(MessageAttachment.file(name, url, "", ""));
            }
        }
        Matcher rawUrls = RAW_URL_PATTERN.matcher(text == null ? "" : text);
        while (rawUrls.find()) {
            String url = rawUrls.group().replaceAll("[,，。)）]+$", "");
            if (looksLikeFileUrl(url)) {
                files.add(MessageAttachment.file(fileNameFromUrl(url), url, "", ""));
            }
        }
        return files;
    }

    private boolean looksLikeFileUrl(String url) {
        return FILE_URL_PATTERN.matcher(url == null ? "" : url).find();
    }

    private String fileNameFromUrl(String url) {
        try {
            String path = Uri.parse(url).getLastPathSegment();
            return path == null || path.isEmpty() ? "文件" : path;
        } catch (Exception ignored) {
            return "文件";
        }
    }

    private void addAttachmentIfNew(List<MessageAttachment> attachments, MessageAttachment candidate) {
        for (MessageAttachment attachment : attachments) {
            if (!candidate.url.isEmpty() && candidate.url.equals(attachment.url)) {
                return;
            }
            if (!candidate.dataUrl.isEmpty() && candidate.dataUrl.equals(attachment.dataUrl)) {
                return;
            }
        }
        attachments.add(candidate);
    }

    private void renderAttachment(LinearLayout bubble, MessageAttachment attachment, boolean mine) {
        if ("image".equals(attachment.type)) {
            renderImageAttachment(bubble, attachment, mine);
        } else {
            renderFileAttachment(bubble, attachment, mine);
        }
    }

    private void renderImageAttachment(LinearLayout bubble, MessageAttachment attachment, boolean mine) {
        ImageView imageView = new ImageView(this);
        imageView.setAdjustViewBounds(true);
        imageView.setMaxHeight(dp(260));
        imageView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        imageView.setBackground(makePanelBackground(mine ? Color.rgb(23, 96, 205) : Color.rgb(248, 250, 253), dp(8), 1, mine ? Color.rgb(99, 154, 230) : Color.rgb(226, 232, 240)));
        if (attachment.bitmap != null) {
            imageView.setImageBitmap(attachment.bitmap);
        } else {
            Bitmap decoded = decodeBitmapFromDataUrl(attachment.dataUrl);
            if (decoded != null) {
                imageView.setImageBitmap(decoded);
            } else if (!attachment.url.isEmpty()) {
                imageView.setImageResource(getApplicationInfo().icon);
                loadRemoteImage(imageView, attachment.url);
            } else {
                imageView.setImageResource(getApplicationInfo().icon);
            }
        }
        if (!attachment.url.isEmpty()) {
            imageView.setOnClickListener(view -> openUrl(attachment.url));
            imageView.setClickable(true);
        }
        LinearLayout.LayoutParams imageParams = new LinearLayout.LayoutParams(dp(228), LinearLayout.LayoutParams.WRAP_CONTENT);
        imageParams.topMargin = dp(8);
        bubble.addView(imageView, imageParams);
    }

    private Bitmap decodeBitmapFromDataUrl(String dataUrl) {
        if (dataUrl == null || !dataUrl.startsWith("data:image/") || !dataUrl.contains(",")) {
            return null;
        }
        try {
            String base64 = dataUrl.substring(dataUrl.indexOf(',') + 1);
            byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        } catch (Exception ignored) {
            return null;
        }
    }

    private void loadRemoteImage(ImageView imageView, String url) {
        executor.execute(() -> {
            try (InputStream stream = new URL(url).openStream()) {
                Bitmap bitmap = BitmapFactory.decodeStream(stream);
                if (bitmap != null) {
                    runOnUiThread(() -> imageView.setImageBitmap(bitmap));
                }
            } catch (Exception exception) {
                runOnUiThread(() -> imageView.setAlpha(0.65f));
            }
        });
    }

    private void renderFileAttachment(LinearLayout bubble, MessageAttachment attachment, boolean mine) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(10), dp(9), dp(10), dp(9));
        card.setBackground(makePanelBackground(mine ? Color.rgb(23, 96, 205) : Color.rgb(248, 250, 253), dp(10), 1, mine ? Color.rgb(99, 154, 230) : Color.rgb(226, 232, 240)));
        card.setClickable(true);
        card.setFocusable(true);
        card.setOnClickListener(view -> {
            if (!attachment.url.isEmpty()) {
                openUrl(attachment.url);
            } else {
                copyMessageToClipboard(buildAttachmentCopyLine(attachment));
            }
        });

        TextView title = new TextView(this);
        title.setText("文件 · " + (attachment.name.isEmpty() ? "未命名文件" : attachment.name));
        title.setTextSize(14);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(mine ? Color.WHITE : Color.rgb(29, 36, 48));
        card.addView(title);

        TextView meta = new TextView(this);
        String metaText = attachment.mimeType.isEmpty() ? "点击打开或复制链接" : attachment.mimeType;
        if (!attachment.size.isEmpty()) {
            metaText += " · " + attachment.size;
        }
        meta.setText(metaText);
        meta.setTextSize(12);
        meta.setTextColor(mine ? Color.rgb(219, 238, 255) : Color.rgb(104, 112, 126));
        meta.setPadding(0, dp(3), 0, 0);
        card.addView(meta);

        LinearLayout.LayoutParams params = matchWrap();
        params.topMargin = dp(8);
        bubble.addView(card, params);
    }

    private void openUrl(String url) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            startActivity(intent);
        } catch (Exception exception) {
            appendLog("无法打开链接：" + exception.getMessage());
        }
    }

    private void copyMessageToClipboard(String text) {
        ClipboardManager manager = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (manager == null) {
            appendLog("复制失败：系统剪贴板不可用。");
            return;
        }
        manager.setPrimaryClip(ClipData.newPlainText("元宵聊天内容", text == null ? "" : text));
        appendLog("已复制本条聊天内容。");
    }

    private String buildCopyText(String text, List<MessageAttachment> attachments) {
        StringBuilder builder = new StringBuilder(text == null ? "" : text.trim());
        for (MessageAttachment attachment : attachments) {
            if (builder.length() > 0) {
                builder.append("\n");
            }
            builder.append(buildAttachmentCopyLine(attachment));
        }
        return builder.toString();
    }

    private String buildAttachmentCopyLine(MessageAttachment attachment) {
        String label = "image".equals(attachment.type) ? "图片" : "文件";
        String name = attachment.name == null || attachment.name.isEmpty() ? label : attachment.name;
        String url = attachment.url == null || attachment.url.isEmpty() ? attachment.dataUrl : attachment.url;
        return url == null || url.isEmpty() ? "[" + label + "] " + name : "[" + label + "] " + name + " " + url;
    }

    private String attachmentsSearchText(List<MessageAttachment> attachments) {
        StringBuilder builder = new StringBuilder();
        for (MessageAttachment attachment : attachments) {
            builder.append(' ')
                    .append(attachment.name)
                    .append(' ')
                    .append(attachment.url)
                    .append(' ')
                    .append(attachment.mimeType);
        }
        return builder.toString();
    }

    private boolean hasImageAttachment(List<MessageAttachment> attachments) {
        for (MessageAttachment attachment : attachments) {
            if ("image".equals(attachment.type)) {
                return true;
            }
        }
        return false;
    }

    private List<MessageAttachment> attachmentsFromMessage(JSONObject message) {
        List<MessageAttachment> attachments = new ArrayList<>();
        attachments.addAll(attachmentsFromJson(message.optJSONArray("images")));
        attachments.addAll(attachmentsFromJson(message.optJSONArray("files")));
        attachments.addAll(attachmentsFromJson(message.optJSONArray("attachments")));
        attachments.addAll(attachmentsFromJson(message.optJSONArray("links")));
        return attachments;
    }

    private List<MessageAttachment> attachmentsFromJson(JSONArray array) {
        List<MessageAttachment> attachments = new ArrayList<>();
        if (array == null) {
            return attachments;
        }
        for (int i = 0; i < array.length(); i++) {
            JSONObject item = array.optJSONObject(i);
            if (item == null) {
                continue;
            }
            MessageAttachment attachment = attachmentFromJson(item);
            if (attachment != null) {
                attachments.add(attachment);
            }
        }
        return attachments;
    }

    private MessageAttachment attachmentFromJson(JSONObject item) {
        String dataUrl = item.optString("data_url", "");
        String url = item.optString("url", item.optString("href", ""));
        String mimeType = item.optString("mime_type", item.optString("mime", ""));
        String type = item.optString("type", "");
        String name = item.optString("name", item.optString("filename", item.optString("alt", "")));
        String size = item.optString("size", item.optString("size_text", ""));
        boolean image = "image".equals(type) || mimeType.startsWith("image/") || dataUrl.startsWith("data:image/") || url.matches("(?i).*\\.(png|jpg|jpeg|webp|gif)(\\?|#|$)");
        if (image) {
            return MessageAttachment.image(name.isEmpty() ? "图片" : name, url, dataUrl, null);
        }
        return MessageAttachment.file(name.isEmpty() ? fileNameFromUrl(url) : name, url, mimeType, size);
    }

    private GradientDrawable makeBubbleBackground(boolean mine, boolean highlighted) {
        GradientDrawable drawable = new GradientDrawable();
        if (highlighted) {
            drawable.setColor(mine ? Color.rgb(23, 96, 205) : Color.rgb(255, 248, 215));
        } else {
            drawable.setColor(mine ? Color.rgb(31, 111, 235) : Color.WHITE);
        }
        drawable.setCornerRadius(dp(10));
        if (highlighted) {
            drawable.setStroke(dp(2), Color.rgb(242, 184, 36));
        } else if (!mine) {
            drawable.setStroke(1, Color.rgb(226, 230, 238));
        }
        return drawable;
    }

    private void scrollToBottom(ScrollView targetScrollView) {
        targetScrollView.post(() -> targetScrollView.fullScroll(View.FOCUS_DOWN));
    }

    private String stamp() {
        return new SimpleDateFormat("HH:mm:ss", Locale.CHINA).format(new Date());
    }

    private String nowLocalIso() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.CHINA).format(new Date());
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "元宵消息",
                NotificationManager.IMPORTANCE_HIGH
        );
        channel.setDescription("嫦娥的新回复");
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.createNotificationChannel(channel);
        }
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < 33) {
            return;
        }
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQUEST_POST_NOTIFICATIONS);
        }
    }

    private void showIncomingNotification(String reply, boolean hasImage) {
        showIncomingNotification("嫦娥有新回复", reply, hasImage);
    }

    private void showIncomingNotification(String title, String reply, boolean hasImage) {
        String safeTitle = title == null || title.trim().isEmpty() ? "嫦娥有新回复" : title.trim();
        String summary = hasImage ? "收到图片回复" : reply;
        if (summary == null || summary.trim().isEmpty()) {
            summary = "嫦娥有新回复";
        }
        if (summary.length() > 90) {
            summary = summary.substring(0, 90) + "...";
        }
        showInAppNotice(safeTitle, summary);

        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            appendLog("系统拦截了通知：请先允许元宵发送通知。");
            return;
        }
        if (!manager.areNotificationsEnabled()) {
            appendLog("系统总通知开关已关闭：请在手机设置里允许元宵通知。");
            return;
        }

        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
                : new Notification.Builder(this);
        builder.setSmallIcon(getApplicationInfo().icon)
                .setContentTitle(safeTitle)
                .setContentText(summary)
                .setStyle(new Notification.BigTextStyle().bigText(summary))
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setWhen(System.currentTimeMillis())
                .setOnlyAlertOnce(true)
                .setPriority(Notification.PRIORITY_HIGH)
                .setDefaults(Notification.DEFAULT_SOUND | Notification.DEFAULT_VIBRATE);

        manager.notify(notificationId++, builder.build());
    }

    private void showInAppNotice(String title, String body) {
        if (noticeBanner == null) {
            return;
        }
        String safeBody = body == null ? "" : body.trim();
        noticeBanner.setText(title + (safeBody.isEmpty() ? "" : "\n" + safeBody));
        noticeBanner.setVisibility(View.VISIBLE);
        noticeHandler.removeCallbacks(hideNoticeRunnable);
        noticeHandler.postDelayed(hideNoticeRunnable, 5200L);
    }

    private static class ImagePayload {
        final Bitmap bitmap;
        final String base64;
        final String mimeType;
        final int sizeBytes;

        ImagePayload(Bitmap bitmap, String base64, String mimeType, int sizeBytes) {
            this.bitmap = bitmap;
            this.base64 = base64;
            this.mimeType = mimeType;
            this.sizeBytes = sizeBytes;
        }
    }

    private static class MessageAttachment {
        final String type;
        final String name;
        final String url;
        final String dataUrl;
        final String mimeType;
        final String size;
        final Bitmap bitmap;

        MessageAttachment(String type, String name, String url, String dataUrl, String mimeType, String size, Bitmap bitmap) {
            this.type = type == null ? "file" : type;
            this.name = name == null ? "" : name;
            this.url = url == null ? "" : url;
            this.dataUrl = dataUrl == null ? "" : dataUrl;
            this.mimeType = mimeType == null ? "" : mimeType;
            this.size = size == null ? "" : size;
            this.bitmap = bitmap;
        }

        static MessageAttachment image(String name, String url, String dataUrl, Bitmap bitmap) {
            return new MessageAttachment("image", name, url, dataUrl, "image", "", bitmap);
        }

        static MessageAttachment file(String name, String url, String mimeType, String size) {
            return new MessageAttachment("file", name, url, "", mimeType, size, null);
        }
    }

    private static class ReleaseGroup {
        final String title;
        final List<ReleaseEntry> entries = new ArrayList<>();
        boolean expanded;

        ReleaseGroup(String title) {
            this.title = title;
        }
    }

    private static class ReleaseEntry {
        final String version;
        final String summary;

        ReleaseEntry(String version, String summary) {
            this.version = version;
            this.summary = summary;
        }
    }

    private static class ChatRecord {
        final View row;
        final LinearLayout bubble;
        final boolean mine;
        final String searchText;

        ChatRecord(View row, LinearLayout bubble, boolean mine, String searchText) {
            this.row = row;
            this.bubble = bubble;
            this.mine = mine;
            this.searchText = searchText;
        }
    }

    private static class MainChatMessage {
        final String speaker;
        final String text;
        final boolean mine;
        final String timeLabel;
        final List<MessageAttachment> attachments;

        MainChatMessage(String speaker, String text, boolean mine, String timeLabel, List<MessageAttachment> attachments) {
            this.speaker = speaker == null ? "" : speaker;
            this.text = text == null ? "" : text;
            this.mine = mine;
            this.timeLabel = timeLabel == null ? "" : timeLabel;
            this.attachments = attachments == null ? new ArrayList<>() : attachments;
        }
    }

    private static class SessionMergeResult {
        boolean changed;
        boolean needsFullRender;
        int addedCount;
        boolean hasNewAssistantMessage;
        String newestAssistantText = "";
        final List<SessionChatMessage> appendedMessages = new ArrayList<>();
    }

    private static class SessionChatMessage {
        String id;
        String speaker;
        String text;
        boolean mine;
        List<MessageAttachment> attachments;
        long order;
        String createdAt;

        SessionChatMessage(
                String id,
                String speaker,
                String text,
                boolean mine,
                List<MessageAttachment> attachments,
                long order,
                String createdAt
        ) {
            this.id = id == null ? "" : id;
            this.speaker = speaker == null ? "" : speaker;
            this.text = text == null ? "" : text;
            this.mine = mine;
            this.attachments = attachments == null ? new ArrayList<>() : new ArrayList<>(attachments);
            this.order = order;
            this.createdAt = createdAt == null ? "" : createdAt;
        }
    }
}
