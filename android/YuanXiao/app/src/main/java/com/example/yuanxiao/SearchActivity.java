package com.example.yuanxiao;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Locale;

public class SearchActivity extends Activity {
    public static final String EXTRA_CHAT_HISTORY = "chat_history";

    private EditText queryInput;
    private TextView statusView;
    private LinearLayout resultList;
    private final ArrayList<String> chatHistory = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Intent intent = getIntent();
        ArrayList<String> history = intent.getStringArrayListExtra(EXTRA_CHAT_HISTORY);
        if (history != null) {
            chatHistory.addAll(history);
        }
        buildUi();
    }

    @Override
    public void onBackPressed() {
        finish();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(12), dp(12), dp(12));
        root.setBackgroundColor(Color.rgb(246, 247, 251));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(14), dp(12), dp(14), dp(12));
        header.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(228, 233, 241)));

        TextView backButton = makeChip("返回", Color.rgb(236, 243, 249), Color.rgb(38, 83, 111));
        backButton.setOnClickListener(view -> finish());
        header.addView(backButton, new LinearLayout.LayoutParams(dp(68), dp(42)));

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);
        titleBlock.setPadding(dp(10), 0, 0, 0);

        TextView title = new TextView(this);
        title.setText("聊天记录搜索");
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(26, 32, 43));
        titleBlock.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("查找元宵和嫦娥的历史对话");
        subtitle.setTextSize(12);
        subtitle.setTextColor(Color.rgb(91, 101, 116));
        titleBlock.addView(subtitle);
        header.addView(titleBlock, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(header);

        LinearLayout searchBar = new LinearLayout(this);
        searchBar.setOrientation(LinearLayout.HORIZONTAL);
        searchBar.setGravity(Gravity.CENTER_VERTICAL);
        searchBar.setPadding(dp(10), dp(10), dp(10), dp(10));
        searchBar.setBackground(makePanelBackground(Color.WHITE, dp(18), 1, Color.rgb(228, 233, 241)));
        LinearLayout.LayoutParams searchBarParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        searchBarParams.topMargin = dp(10);

        queryInput = new EditText(this);
        queryInput.setHint("输入关键词");
        queryInput.setSingleLine(true);
        queryInput.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        queryInput.setTextSize(15);
        queryInput.setTextColor(Color.rgb(29, 36, 48));
        queryInput.setHintTextColor(Color.rgb(138, 147, 162));
        queryInput.setPadding(dp(12), 0, dp(12), 0);
        queryInput.setBackground(makePanelBackground(Color.rgb(246, 248, 252), dp(14), 1, Color.rgb(229, 234, 242)));
        queryInput.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                runSearch();
                return true;
            }
            return false;
        });
        searchBar.addView(queryInput, new LinearLayout.LayoutParams(0, dp(44), 1f));

        TextView searchButton = makeChip("查找", Color.rgb(31, 111, 235), Color.WHITE);
        searchButton.setOnClickListener(view -> runSearch());
        LinearLayout.LayoutParams searchParams = new LinearLayout.LayoutParams(dp(76), dp(44));
        searchParams.leftMargin = dp(8);
        searchBar.addView(searchButton, searchParams);
        root.addView(searchBar, searchBarParams);

        statusView = new TextView(this);
        statusView.setText("输入关键词后开始搜索");
        statusView.setTextSize(12);
        statusView.setTextColor(Color.rgb(104, 112, 126));
        statusView.setPadding(dp(4), dp(8), dp(4), dp(4));
        root.addView(statusView);

        ScrollView resultScroll = new ScrollView(this);
        resultList = new LinearLayout(this);
        resultList.setOrientation(LinearLayout.VERTICAL);
        resultList.setPadding(0, dp(4), 0, 0);
        resultScroll.addView(resultList, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT,
                ScrollView.LayoutParams.WRAP_CONTENT
        ));
        LinearLayout.LayoutParams resultParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
        );
        resultParams.topMargin = dp(10);
        root.addView(resultScroll, resultParams);

        setContentView(root);
    }

    private void runSearch() {
        String query = queryInput.getText().toString().trim().toLowerCase(Locale.ROOT);
        resultList.removeAllViews();
        if (query.isEmpty()) {
            statusView.setText("请输入关键词");
            return;
        }
        int matchCount = 0;
        for (String record : chatHistory) {
            if (!record.contains(query)) {
                continue;
            }
            matchCount++;
            resultList.addView(makeResultCard(record, matchCount));
        }
        if (matchCount == 0) {
            statusView.setText("没有找到匹配记录");
        } else {
            statusView.setText("找到 " + matchCount + " 条记录");
        }
    }

    private View makeResultCard(String text, int index) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(12), dp(10), dp(12), dp(10));
        card.setBackground(makePanelBackground(Color.WHITE, dp(16), 1, Color.rgb(228, 233, 241)));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.bottomMargin = dp(8);

        TextView title = new TextView(this);
        title.setText("结果 " + index);
        title.setTextSize(13);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(31, 111, 235));
        card.addView(title);

        TextView content = new TextView(this);
        content.setText(text);
        content.setTextSize(14);
        content.setTextColor(Color.rgb(43, 50, 63));
        content.setPadding(0, dp(6), 0, 0);
        card.addView(content);
        return card;
    }

    private TextView makeChip(String text, int backgroundColor, int textColor) {
        TextView chip = new TextView(this);
        chip.setText(text);
        chip.setTextSize(14);
        chip.setTypeface(Typeface.DEFAULT_BOLD);
        chip.setTextColor(textColor);
        chip.setGravity(Gravity.CENTER);
        chip.setIncludeFontPadding(false);
        chip.setBackground(makePanelBackground(backgroundColor, dp(15), 0, Color.TRANSPARENT));
        return chip;
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

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
