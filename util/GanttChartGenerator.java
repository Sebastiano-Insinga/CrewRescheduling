package util;

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

    /**
     * Genera un diagramma di Gantt dalle duty fornite e lo salva come immagine PNG.
     *
     * @param filename Il percorso/nome del file di output (es. "results/gantt.png")
     * @param duties   La lista di Duty da visualizzare
     */
    public static void plotGanttChart(String filename, List<Duty> duties) {
        // 1. Creazione del Dataset
        IntervalCategoryDataset dataset = createDataset(duties);

        // 2. Creazione del Grafico
        JFreeChart chart = ChartFactory.createGanttChart(
                "Railway Crew Scheduling Duties", // Titolo del grafico
                "Duties",                         // Etichetta asse Y (Categorie)
                "Time (Minutes from midnight)",   // Etichetta asse X (Tempo)
                dataset,                          // Dati
                true,                             // Legenda
                true,                             // Tooltips
                false                             // URL
        );

        // 3. Personalizzazione del Plot (Opzionale, per renderlo simile a Matplotlib)
        CategoryPlot plot = (CategoryPlot) chart.getPlot();
        GanttRenderer renderer = (GanttRenderer) plot.getRenderer();
        
        // Imposta lo spessore delle barre
        renderer.setMaximumBarWidth(0.1); 
        
        // Imposta il colore blu (simile a "tab:blue" di matplotlib)
        renderer.setSeriesPaint(0, new Color(31, 119, 180)); 

        // 4. Salvataggio dell'immagine
        try {
            // Calcola un'altezza dinamica in base al numero di duty, come nel codice Python
            int height = 150 + (duties.size() * 15); 
            int width = 2000; // Larghezza fissa ampia

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

            // I tuoi tempi sono in minuti (int). JFreeChart usa oggetti Date.
            // Dobbiamo trovare il min start e max end per la barra principale del Duty.
            long minStart = Long.MAX_VALUE;
            long maxEnd = Long.MIN_VALUE;

            // Calcolo estremi del duty
            for (Task t : duty.getTasks()) {
                if (t.getStartTime() < minStart) minStart = t.getStartTime();
                if (t.getEndTime() > maxEnd) maxEnd = t.getEndTime();
            }

            // Crea il task "contenitore" per la riga del Duty (Barra principale)
            // Nota: moltiplichiamo per 60000 per convertire minuti in millisecondi per l'oggetto Date
            org.jfree.data.gantt.Task mainDutyTask = new org.jfree.data.gantt.Task(
                    dutyLabel,
                    new Date(minStart * 60000L),
                    new Date(maxEnd * 60000L)
            );

            // Aggiungi i sotto-task (i segmenti effettivi che rappresentano i task ferroviari)
            for (Task t : duty.getTasks()) {
                org.jfree.data.gantt.Task subTask = new org.jfree.data.gantt.Task(
                        "T" + t.getID(), // Label del sub-task
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
