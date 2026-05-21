package util;

// GanttChartGenerator disabilitato (richiede jfreechart.jar non disponibile)
/*
import columnGeneration.Duty;
import instance.Task;
import org.jfree.chart.ChartFactory;
import org.jfree.chart.ChartUtils;
import org.jfree.chart.JFreeChart;
import org.jfree.chart.plot.CategoryPlot;
import org.jfree.chart.renderer.category.GanttRenderer;
import org.jfree.data.category.IntervalCategoryDataset;
import org.jfree.data.gantt.TaskSeries;
import org.jfree.data.gantt.TaskSeriesCollection;

import java.awt.*;
import java.io.File;
import java.io.IOException;
import java.util.Date;
import java.util.List;

public class GanttChartGenerator {

    public static void plotGanttChart(String filename, List<Duty> duties) {
        IntervalCategoryDataset dataset = createDataset(duties);

        JFreeChart chart = ChartFactory.createGanttChart(
                "Railway Crew Scheduling Duties",
                "Duties",
                "Time (Minutes from midnight)",
                dataset,
                true,
                true,
                false
        );

        CategoryPlot plot = (CategoryPlot) chart.getPlot();
        GanttRenderer renderer = (GanttRenderer) plot.getRenderer();
        renderer.setMaximumBarWidth(0.1);
        renderer.setSeriesPaint(0, new Color(31, 119, 180));

        try {
            int height = 150 + (duties.size() * 15);
            int width = 2000;
            File chartFile = new File(filename);
            ChartUtils.saveChartAsPNG(chartFile, chart, width, height);
            System.out.println("Gantt chart salvato in: " + chartFile.getAbsolutePath());
        } catch (IOException e) {
            System.err.println("Errore durante il salvataggio del Gantt chart: " + e.getMessage());
        }
    }

    private static IntervalCategoryDataset createDataset(List<Duty> duties) {
        TaskSeries series = new TaskSeries("Scheduled Tasks");

        for (Duty duty : duties) {
            String dutyLabel = "D" + duty.getID();
            long minStart = Long.MAX_VALUE;
            long maxEnd = Long.MIN_VALUE;

            for (Task t : duty.getTasks()) {
                if (t.getStartTime() < minStart) minStart = t.getStartTime();
                if (t.getEndTime() > maxEnd) maxEnd = t.getEndTime();
            }

            org.jfree.data.gantt.Task mainDutyTask = new org.jfree.data.gantt.Task(
                    dutyLabel,
                    new Date(minStart * 60000L),
                    new Date(maxEnd * 60000L)
            );

            for (Task t : duty.getTasks()) {
                org.jfree.data.gantt.Task subTask = new org.jfree.data.gantt.Task(
                        "T" + t.getID(),
                        new Date((long)t.getStartTime() * 60000L),
                        new Date((long)t.getEndTime() * 60000L)
                );
                mainDutyTask.addSubtask(subTask);
            }

            series.add(mainDutyTask);
        }

        TaskSeriesCollection collection = new TaskSeriesCollection();
        collection.add(series);
        return collection;
    }
}
*/

public class GanttChartGenerator {
    // disabilitato
}
