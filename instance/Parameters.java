package instance;

/**
 * Simple class to store some parameters.
 * 
 * @author B.T.C. van Rossum
 */
public class Parameters
{
	// Costs.
	public static final int FIXED_DUTY_COST = 900;
	public static final int VARIABLE_DUTY_COST = 1;

	// Constraints.
	//public static final int MAX_TIME_WITHOUT_BREAK = 5*60 +30;
	public static final int MAX_TIME_WITHOUT_BREAK = 12*60;
	public static final int MIN_BREAK_LENGTH = 0;
	public static final int MIN_TRANSITION_TIME = 0;
	public static final int MAX_DUTY_LENGTH = 12 * 60 ;
	//12*60
	
	// Instance generation.
	public static final int NUM_DEPOTS = 10;
	public static final int NUM_STATIONS = 10;
	public static final int MAX_START_TIME = 24 * 60;
	public static final int MIN_TASK_LENGTH = 20;
	public static final int MAX_TASK_LENGTH = 90;

	// Numerical.
	public static final double PRECISION = 0.0001;

	// Column generation.
	public static final double SIMILARITY_THRESHOLD = 1;

	//NUOVO
	public static final double PENALTY=1;

}
