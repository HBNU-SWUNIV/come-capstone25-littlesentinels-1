package com.example.growvision20;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import androidx.recyclerview.widget.RecyclerView;

import com.example.growvision20.databinding.ItemGrowthLogRecyclerBinding;

import java.util.ArrayList;

public class GrowthLogAdapter extends RecyclerView.Adapter<GrowthLogAdapter.mViewHolder> {
    private ArrayList<GrowthLogData> dataset;
    public GrowthLogAdapter(ArrayList<GrowthLogData> dataset) {
        this.dataset = dataset;
    }

    @Override
    public mViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        return new mViewHolder(
                ItemGrowthLogRecyclerBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false)
        );
    }

    @Override
    public void onBindViewHolder(mViewHolder holder, int position) {
        holder.onBind(dataset.get(position));
        holder.bind.tvDay.setOnClickListener(view -> {
            if (holder.bind.listItems.getVisibility() == View.VISIBLE)
                holder.bind.listItems.setVisibility(View.GONE);
            else
                holder.bind.listItems.setVisibility(View.VISIBLE);
        });
    }

    @Override
    public int getItemCount() {
        if (dataset != null)
            return dataset.size();
        else
            return 0;
    }

    public class mViewHolder extends RecyclerView.ViewHolder{
        private ItemGrowthLogRecyclerBinding bind;
        mViewHolder (ItemGrowthLogRecyclerBinding bind) {
            super(bind.getRoot());
            this.bind = bind;
        }
        private void onBind(GrowthLogData item) {
            bind.tvDay.setText(item.datetime);
            bind.tvCumulTotal.setText(item.n_cumul_total);
            bind.tvCurrentTotal.setText(item.n_current_total);
            bind.tvCumulMature.setText(item.n_cumul_mature);
            bind.tvCurrentMature.setText(item.n_current_mature);
            bind.tvCumulRatio.setText(item.n_cumul_ratio);
            bind.tvCurrentRatio.setText(item.n_current_ratio);
            bind.tvCumulHarvest.setText(item.n_cumul_harvest);
            bind.tvCurrentHarvest.setText(item.n_current_harvest);
        }
    }
}
