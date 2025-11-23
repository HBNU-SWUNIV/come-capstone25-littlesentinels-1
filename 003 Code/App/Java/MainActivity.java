package com.example.growvision20;

import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import androidx.databinding.DataBindingUtil;
import androidx.lifecycle.ViewModelProvider;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.exoplayer.ExoPlayer;

import com.example.growvision20.databinding.ActivityMainBinding;
import com.example.growvision20.databinding.DialogMainBinding;
import com.google.firebase.firestore.DocumentReference;
import com.google.firebase.firestore.FirebaseFirestore;

public class MainActivity extends AppCompatActivity {
    private ActivityMainBinding bind;
    private SharedPreferences preferences;
    private String RTSP = null;
    private ExoPlayer player;
    private HarvestViewModel vm;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        bind = DataBindingUtil.setContentView(this, R.layout.activity_main);

        setScreen();
        initVM();
        getDataFromFirestore();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu_main, menu);
        return super.onCreateOptionsMenu(menu);
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.menu_log) {
            startActivity(new Intent(this, GrowthLogActivity.class));
            return true;
        }
        else if (item.getItemId() == R.id.menu_connection) {
            showDialog();
            return true;
        }
        else
            return true;
    }

    @Override
    protected void onStart() {
        super.onStart();
        if (!isFirstExecute())
            initPlayer();
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (RTSP != null)
            releasePlayer();
    }

    private boolean isFirstExecute() {
        preferences = getSharedPreferences("Settings", MODE_PRIVATE);
        if (preferences.contains("Address")) {
            RTSP = preferences.getString("Address", null);
            return false;
        }
        else {
            showDialog();
            return true;
        }
    }
    private void showDialog() {
        AlertDialog.Builder dlg = new AlertDialog.Builder(this);
        DialogMainBinding dlg_main_bind = DialogMainBinding.inflate(getLayoutInflater());
        dlg.setView(dlg_main_bind.getRoot());

        if ((RTSP != null) && (!RTSP.isEmpty()))
            dlg_main_bind.tvAddress.setText("Current = " + RTSP);

        dlg.setNegativeButton("Cancel", null);
        dlg.setPositiveButton("Save", (dialogInterface, i) -> {
            RTSP = dlg_main_bind.etAddress.getText().toString();

            if (!RTSP.isEmpty()) {
                preferences.edit().putString("Address", RTSP).apply();
                initPlayer();
            }
            else {
                RTSP = null;
                Toast.makeText(getApplicationContext(), "Write a RTSP Server Address", Toast.LENGTH_LONG).show();
            }

        });
        dlg.show();
    }

    private boolean isLandscape() {
        return getResources().getConfiguration().orientation == Configuration.ORIENTATION_LANDSCAPE;
    }
    private void hideStatusBar() {
        WindowInsetsControllerCompat bar_controller = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        bar_controller.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        bar_controller.hide(WindowInsetsCompat.Type.systemBars());
    }
    private void setScreen() {
        boolean status_bar_orientation = isLandscape();
        ImageButton btn_full_screen = findViewById(R.id.btn_full_screen);
        ImageButton btn_restart = findViewById(R.id.btn_restart);
        Button btn_live = findViewById(R.id.btn_live);

        btn_full_screen.setOnClickListener(view -> {
            if (status_bar_orientation)
                setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
            else
                setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE);
        });

        btn_restart.setOnClickListener(view -> initPlayer());
        btn_live.setOnClickListener(view -> {
            if (player != null)
                player.seekToDefaultPosition();
        });

        if (status_bar_orientation) {
            hideStatusBar();
            btn_full_screen.setImageResource(R.drawable.ic_fullscreen_exit);
        }
        else {
            setSupportActionBar(bind.toolbar);
            btn_full_screen.setImageResource(R.drawable.ic_fullscreen);
        }
    }

    private void initPlayer() {
        releasePlayer();

        player = new ExoPlayer.Builder(this).build();
        bind.playerView.setPlayer(player);
        MediaItem mediaItem = MediaItem.fromUri(RTSP);
        player.setMediaItem(mediaItem);

        player.addListener(new Player.Listener() {
            @Override
            public void onPlaybackStateChanged(int playbackState) {
                if (playbackState == Player.STATE_IDLE)
                    bind.loadingIndicator.setVisibility(View.GONE);

                else if (playbackState == Player.STATE_BUFFERING)
                    bind.loadingIndicator.setVisibility(View.VISIBLE);

                else if (playbackState == Player.STATE_READY)
                    bind.loadingIndicator.setVisibility(View.GONE);

                else if (playbackState == Player.STATE_ENDED)
                    releasePlayer();
            }
        });

        player.prepare();
        player.play();
    }
    private void releasePlayer() {
        if (player != null) {
            player.release();
            player = null;
        }
    }

    private void initVM() {
        vm = new ViewModelProvider(this).get(HarvestViewModel.class);
        bind.setViewModel(vm);
        bind.setLifecycleOwner(this);
    }
    private void getDataFromFirestore() {
        FirebaseFirestore db = FirebaseFirestore.getInstance();

        db.collection("Harvest_Data").document("Data")
                .addSnapshotListener((value, error) ->
                        vm.setData(new HarvestData(value.getLong("n_total"), value.getLong("n_mature"),
                                                   value.getLong("n_immature"), value.getLong("n_harvest"))));
    }
}