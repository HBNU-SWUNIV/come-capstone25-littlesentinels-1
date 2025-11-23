package com.example.growvision20;

import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;

import com.example.growvision20.databinding.ActivityGrowthLogBinding;
import com.google.android.gms.tasks.OnCompleteListener;
import com.google.android.gms.tasks.Task;
import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.firestore.QueryDocumentSnapshot;
import com.google.firebase.firestore.QuerySnapshot;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

public class GrowthLogActivity extends AppCompatActivity {
    private ActivityGrowthLogBinding bind;
    private ArrayList<GrowthLogData> dataset;
    private GrowthLogAdapter adapter;
    FirebaseFirestore db = FirebaseFirestore.getInstance();
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        bind = ActivityGrowthLogBinding.inflate(getLayoutInflater());
        setContentView(bind.getRoot());
        setSupportActionBar(bind.toolbar);
        getSupportActionBar().setTitle("Growth Log");

        setAdapter();
        getDataFromFirestore();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu_growth_log, menu);
        return super.onCreateOptionsMenu(menu);
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        if (item.getItemId() == R.id.menu_clear) {
            AlertDialog.Builder builder = new AlertDialog.Builder(GrowthLogActivity.this);
            builder.setCustomTitle(getLayoutInflater().inflate(R.layout.dialog_growth_log_title, null))
                    .setMessage("Do you want to clear the logs?")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Clear", (dialogInterface, i) -> clearFirestoreData())
                    .create()
                    .show();
            return true;
        }
        else return false;
    }

    private void setAdapter() {
        dataset = new ArrayList<>();
        adapter = new GrowthLogAdapter(dataset);
        bind.recyclerView.setLayoutManager(new LinearLayoutManager(this));
        bind.recyclerView.setAdapter(adapter);
    }
    private void getDataFromFirestore() {
        SimpleDateFormat formatter = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.KOREAN);
        formatter.setTimeZone(TimeZone.getTimeZone("Asia/Seoul"));

        db.collection("Growth_Log")
                .orderBy("datetime")
                .get()
                .addOnCompleteListener(task -> {
                    if (task.isSuccessful()) {
                        for (QueryDocumentSnapshot doc: task.getResult()) {
                            dataset.add(new GrowthLogData(
                                    formatter.format(doc.getTimestamp("datetime").toDate()),
                                    doc.getLong("n_cumul_total"),
                                    doc.getLong("n_current_total"),
                                    doc.getLong("n_cumul_mature"),
                                    doc.getLong("n_current_mature"),
                                    doc.getLong("n_cumul_harvest"),
                                    doc.getLong("n_current_harvest")));
                        }
                        adapter.notifyDataSetChanged();
                    }
                });
    }

    private void clearFirestoreData() {
        db.collection("Growth_Log")
                .get()
                .addOnCompleteListener(task -> {
                    for (QueryDocumentSnapshot doc: task.getResult()) {
                        doc.getReference().delete();
                    }
                });
    }
}
